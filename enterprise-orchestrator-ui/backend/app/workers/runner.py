"""
RQ worker task for orchestration job execution.
This module is imported by the RQ worker process — keep it serialization-safe.
All job configs and SQL files are read from GitHub — no local folder dependency.
"""
import logging
import os
from pathlib import Path
from typing import Any

from app.models import JobStatus
from app.database import SessionLocal
from app.services import db_store
from app.services.sharepoint_publisher import upload_report as sharepoint_upload
from app.services.confluence_publisher import publish_report as confluence_publish
from app.services.report_generator import generate_report, extract_target_tables
from app.services import github_client, dagster_client, montecarlo_client, snowflake_client
from app import config

logger = logging.getLogger(__name__)


def execute_orchestration(job_id: str, job_name: str | None, table_name: str | None, repo: str | None) -> dict[str, Any]:
    """
    Synchronous orchestration entry point called by RQ worker.
    Raises on failure so RQ can apply retry policy automatically.
    """
    db = SessionLocal()
    live_data: dict[str, Any] = {}
    try:
        db_store.update_status(db, job_id, JobStatus.RUNNING, "Worker picked up job")
        logger.info("Job %s: execution started (job_name=%s, table_name=%s, repo=%s)", job_id, job_name, table_name, repo)

        # === Stage 1: Resolve job context from GitHub ===
        logger.info("Job %s: Stage 1 — resolving job context from GitHub", job_id)
        gh_ctx = {}
        job_config = {}
        sql_files: list[tuple[str, str]] = []
        targets: list[str] = []

        if job_name:
            gh_ctx = github_client.get_job_context(job_name, repo)
            live_data["github"] = gh_ctx

            if gh_ctx.get("config"):
                job_config = gh_ctx["config"]
                sql_files = gh_ctx.get("sql_files", [])
                logger.info("Job %s: resolved — source=%s, repo=%s, sql_count=%s",
                             job_id, gh_ctx.get("source"), gh_ctx.get("org_repo"), gh_ctx.get("sql_count"))
            else:
                logger.warning("Job %s: resolution failed — %s", job_id,
                               gh_ctx.get("error", "Could not fetch job config"))
                live_data["github"] = {"source": gh_ctx.get("source", "unknown"), "error": gh_ctx.get("error", "Job not found")}

        # Extract target tables from config (used by MC + Snowflake stages)
        if job_config:
            targets = extract_target_tables(job_config)

        # === Stage 2: ETL lineage (derived from config — no external call) ===
        logger.info("Job %s: Stage 2 — composing ETL lineage from config", job_id)

        # === Stage 3: SQL optimization (skip — no local DQ/ folder) ===
        logger.info("Job %s: Stage 3 — SQL optimization (skipped, no local DQ/)", job_id)

        # === Stage 4: Dagster ops intelligence ===
        logger.info("Job %s: Stage 4 — Dagster ops query", job_id)
        if dagster_client.is_configured() and job_name:
            dagster_data = dagster_client.get_full_ops_intelligence(job_name)
            live_data["dagster"] = dagster_data
            logger.info("Job %s: Dagster — available=%s, job_found=%s",
                         job_id, dagster_data.get("available"), dagster_data.get("job_found"))
        else:
            live_data["dagster"] = {"available": False, "error": "Dagster token not configured"}
            logger.info("Job %s: Dagster not configured", job_id)

        # === Stage 5: Monte Carlo alerts ===
        logger.info("Job %s: Stage 5 — Monte Carlo DQ check", job_id)
        if montecarlo_client.is_configured() and targets:
            mc_data = montecarlo_client.get_full_table_intelligence(targets)
            live_data["montecarlo"] = mc_data
            logger.info("Job %s: Monte Carlo — checked %d tables", job_id, len(mc_data))
        else:
            live_data["montecarlo"] = {}
            if not targets:
                logger.info("Job %s: No target tables for Monte Carlo check", job_id)
            else:
                logger.info("Job %s: Monte Carlo not configured", job_id)

        # === Stage 5b: Snowflake table metadata (optional) ===
        if snowflake_client.is_configured() and targets:
            logger.info("Job %s: Stage 5b — Snowflake metadata", job_id)
            sf_data = snowflake_client.get_full_table_intelligence(targets)
            live_data["snowflake"] = sf_data
            logger.info("Job %s: Snowflake — got metadata for %d tables", job_id, len(sf_data))
        else:
            live_data["snowflake"] = {}

        # === Stage 6: Generate report HTML ===
        logger.info("Job %s: Stage 6 — generating HTML report", job_id)
        report_html = generate_report(
            job_id=job_id,
            job_name=job_name,
            table_name=table_name,
            repo=repo,
            live_data=live_data,
            job_config=job_config,
            sql_files=sql_files,
        )

        # === Stage 7: Save report as .html file ===
        reports_dir = Path(os.getenv("REPORTS_DIR", Path(__file__).resolve().parents[2] / "reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_filename = f"{job_name or table_name or job_id[:8]}_report_{job_id[:8]}.html"
        local_file = reports_dir / report_filename
        local_file.write_text(report_html, encoding="utf-8")
        logger.info("Job %s: Stage 7 — report saved: %s", job_id, local_file)

        # The artifact URL points to the API endpoint that serves the file
        artifact_url = f"http://127.0.0.1:8080/reports/{report_filename}"

        db_store.set_artifact(db, job_id, artifact_url)
        db_store.update_status(db, job_id, JobStatus.COMPLETED, "All stages completed successfully")
        logger.info("Job %s: completed", job_id)

        return {"job_id": job_id, "status": "completed", "artifact_url": artifact_url}

    except Exception as exc:
        db_store.increment_retry(db, job_id)
        db_store.update_status(db, job_id, JobStatus.FAILED, f"Execution failed: {exc}")
        logger.exception("Job %s: failed", job_id)
        raise  # let RQ handle retry
    finally:
        db.close()


def _generate_placeholder_report(job_id: str, job_name: str | None, table_name: str | None, repo: str | None) -> str:
    """Generate a minimal HTML report placeholder. Replace with real report generation."""
    return f"""<!DOCTYPE html>
<html><head><title>Report {job_id[:8]}</title></head>
<body>
<h1>Orchestration Report</h1>
<table>
<tr><td>Job ID</td><td>{job_id}</td></tr>
<tr><td>Job Name</td><td>{job_name or 'N/A'}</td></tr>
<tr><td>Table Name</td><td>{table_name or 'N/A'}</td></tr>
<tr><td>Repo</td><td>{repo or 'auto-detected'}</td></tr>
</table>
<p>Full report content will be generated by orchestration stages.</p>
</body></html>"""


