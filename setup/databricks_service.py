import asyncio
import base64
import json
import logging
import os
import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# ── Direct Databricks REST API helpers (migrated from MCP server) ─────────────

_DATABRICKS_TIMEOUT = httpx.Timeout(10.0, read=60.0)


def _databricks_headers() -> dict:
    token = os.environ.get("DATABRICKS_TOKEN", "")
    token = token.split("#")[0].strip().strip('"').strip("'")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _databricks_base_url() -> str:
    return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


async def _get_run_direct_output(run_id: int) -> dict:
    """GET /api/2.2/jobs/runs/get-output — works for single-task runs."""
    url = f"{_databricks_base_url()}/api/2.2/jobs/runs/get-output"
    async with httpx.AsyncClient(timeout=_DATABRICKS_TIMEOUT, verify=False) as client:
        resp = await client.get(url, headers=_databricks_headers(), params={"run_id": run_id})
        resp.raise_for_status()
        return resp.json()


async def _get_run_export_logs(run_id: int) -> dict:
    """GET /api/2.2/jobs/runs/export — fallback for multi-task runs."""
    url = f"{_databricks_base_url()}/api/2.2/jobs/runs/export"
    async with httpx.AsyncClient(timeout=_DATABRICKS_TIMEOUT, verify=False) as client:
        resp = await client.get(
            url, headers=_databricks_headers(),
            params={"run_id": run_id, "views_to_export": "LOGS"}
        )
        resp.raise_for_status()
        return resp.json()


async def _fetch_databricks_logs(run_id: int) -> dict:
    """
    Fetch Databricks job logs for a run ID.

    Strategy:
    1. Try /jobs/runs/get-output (single-task runs).
    2. Fall back to /jobs/runs/export with LOGS view (multi-task runs).

    Returns a dict with keys: run_id, error, error_trace, notebook_result,
    export_logs, metadata, raw_output.
    """
    result = {"run_id": run_id}

    # Attempt 1: get-output
    try:
        output = await _get_run_direct_output(run_id)
        result["raw_output"] = output

        metadata = output.get("metadata", {})
        result["metadata"] = {
            "run_id": metadata.get("run_id", run_id),
            "job_id": metadata.get("job_id"),
            "task_key": metadata.get("task_key"),
        }
        result["error"] = output.get("error")
        result["error_trace"] = output.get("error_trace")
        notebook = output.get("notebook_output", {})
        result["notebook_result"] = notebook.get("result") if notebook else None

        logger.info("analyze_databricks_job: /get-output succeeded for run_id=%s", run_id)

        # If we got an error/trace that's enough — return immediately
        if result["error"] or result["error_trace"] or result["notebook_result"]:
            return result

        # No meaningful content — check if multi-task run, fall through to export
        logger.info("analyze_databricks_job: /get-output had no error/trace, trying /export for run_id=%s", run_id)

    except httpx.HTTPStatusError as exc:
        multi_task_msg = "Retrieving the output of runs with multiple tasks is not supported"
        if exc.response.status_code == 400 and multi_task_msg in exc.response.text:
            logger.info("analyze_databricks_job: multi-task run detected for run_id=%s, falling back to /export", run_id)
        else:
            logger.error("analyze_databricks_job: /get-output HTTP error for run_id=%s: %s", run_id, exc)
            result["get_output_error"] = f"{exc.response.status_code}: {exc.response.text}"
    except Exception as exc:
        logger.error("analyze_databricks_job: /get-output unexpected error for run_id=%s: %s", run_id, exc)
        result["get_output_error"] = str(exc)

    # Attempt 2: /export with LOGS
    try:
        export_data = await _get_run_export_logs(run_id)
        decoded_logs = []
        for view in export_data.get("views", []):
            if view.get("type") == "LOGS" and view.get("content"):
                try:
                    decoded_logs.append(base64.b64decode(view["content"]).decode("utf-8", errors="replace"))
                except Exception as decode_exc:
                    logger.warning("analyze_databricks_job: log decode error: %s", decode_exc)
                    decoded_logs.append(f"[decode error: {decode_exc}]")

        result["export_logs"] = "\n".join(decoded_logs) if decoded_logs else None

        # Pull state message from export run metadata if available
        run_meta = export_data.get("run", {})
        state = run_meta.get("state", {})
        if state.get("state_message"):
            result["state_message"] = state["state_message"]

        logger.info("analyze_databricks_job: /export succeeded for run_id=%s (%d chars)", run_id, len(result["export_logs"] or ""))

    except Exception as exc:
        logger.error("analyze_databricks_job: /export failed for run_id=%s: %s", run_id, exc)
        result["export_error"] = str(exc)

    return result


def analyze_databricks_job(run_id: int) -> dict:
    """
    Sync entry point — fetch Databricks job logs for a given run ID.

    Tries /jobs/runs/get-output first (single-task), falls back to
    /jobs/runs/export (multi-task). Uses DATABRICKS_HOST and DATABRICKS_TOKEN
    env vars. No MCP server required.

    Args:
        run_id: Databricks job run ID.

    Returns:
        dict with: run_id, error, error_trace, notebook_result,
        export_logs, metadata, state_message (where available).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside an async context (e.g. Django async views)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _fetch_databricks_logs(run_id))
                return future.result()
        else:
            return loop.run_until_complete(_fetch_databricks_logs(run_id))
    except Exception as exc:
        logger.error("analyze_databricks_job: failed for run_id=%s: %s", run_id, exc)
        return {"run_id": run_id, "error": str(exc)}


def get_databricks_job_logs(run_id: int) -> dict:
    """
    Fetch Databricks job run metadata and error output directly via the SDK.

    Uses WorkspaceClient.jobs.get_run() for run-level state and
    WorkspaceClient.jobs.get_run_output() for error messages and stack traces.
    Credentials are read from DATABRICKS_HOST and DATABRICKS_TOKEN env vars.

    Args:
        run_id: Databricks job run ID (integer).

    Returns:
        dict with keys:
          run_id, job_id, job_name, state, life_cycle_state,
          result_state, start_time, end_time, tasks,
          error, error_trace, metadata
    """
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        return {"error": "databricks-sdk is not installed. Run: pip install databricks-sdk"}

    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")

    try:
        kwargs = {}
        if host:
            kwargs["host"] = host
        if token:
            kwargs["token"] = token
        client = WorkspaceClient(**kwargs)
    except Exception as exc:
        logger.error("Failed to initialise WorkspaceClient: %s", exc)
        return {"error": f"Failed to connect to Databricks: {exc}"}

    result: dict = {"run_id": run_id}

    # --- Run-level metadata ---
    try:
        run = client.jobs.get_run(run_id=run_id)
        result["job_id"] = getattr(run, "job_id", None)
        result["job_name"] = None

        # Extract cluster / task info
        tasks = []
        for task in getattr(run, "tasks", []) or []:
            task_info = {
                "task_key": getattr(task, "task_key", None),
                "cluster_instance": None,
                "state": None,
            }
            ci = getattr(task, "cluster_instance", None)
            if ci:
                task_info["cluster_instance"] = {
                    "cluster_id": getattr(ci, "cluster_id", None),
                    "spark_context_id": getattr(ci, "spark_context_id", None),
                }
            ts = getattr(task, "state", None)
            if ts:
                task_info["state"] = {
                    "life_cycle_state": str(getattr(ts, "life_cycle_state", "")),
                    "result_state": str(getattr(ts, "result_state", "")),
                    "state_message": getattr(ts, "state_message", None),
                }
            tasks.append(task_info)
        result["tasks"] = tasks

        state = getattr(run, "state", None)
        if state:
            result["life_cycle_state"] = str(getattr(state, "life_cycle_state", ""))
            result["result_state"] = str(getattr(state, "result_state", ""))
            result["state_message"] = getattr(state, "state_message", None)

        start_time = getattr(run, "start_time", None)
        end_time = getattr(run, "end_time", None)
        result["start_time"] = start_time
        result["end_time"] = end_time

        result["metadata"] = {
            "run_id": run_id,
            "job_id": result.get("job_id"),
        }

        logger.info("get_databricks_job_logs: run metadata fetched for run_id=%s", run_id)
    except Exception as exc:
        logger.error("get_databricks_job_logs: get_run failed for run_id=%s: %s", run_id, exc)
        result["run_fetch_error"] = str(exc)

    # --- Error output (most important for troubleshooting) ---
    try:
        output = client.jobs.get_run_output(run_id=run_id)
        result["error"] = getattr(output, "error", None)
        result["error_trace"] = getattr(output, "error_trace", None)
        notebook_output = getattr(output, "notebook_output", None)
        if notebook_output:
            result["notebook_result"] = getattr(notebook_output, "result", None)
        logger.info("get_databricks_job_logs: run output fetched for run_id=%s", run_id)
    except Exception as exc:
        logger.warning("get_databricks_job_logs: get_run_output failed for run_id=%s: %s", run_id, exc)
        result["output_fetch_error"] = str(exc)

    return result


async def restart_databricks_job(job_id: int | None, job_nm: str | None) -> dict:
    """
    Simulates restarting a Databricks job.
    In a real implementation, this would use the Databricks REST API.
    """
    identifier = job_id
    logger.info(f"Simulating restart for Databricks job: {identifier}")

    # TODO: Implement actual Databricks API call here.
    # Example:
    headers = {"Authorization": f"Bearer {os.getenv('DATABRICKS_TOKEN')}"}
    payload = {"job_id": job_id}
    url = "https://<your-databricks-host>.cloud.databricks.com/api/2.0/jobs/run-now"
    logger.debug(f"POST {url} with payload: {payload} and headers: {headers}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers
            )
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            print("Response JSON:", response.json())
            print("Response Raise Status:", response.raise_for_status())
            response.raise_for_status()
            return response.json(),response.status_code
        except Exception as e:
            logger.error(f"Error during Databricks API call: {e}")
            raise

    # For now, return a mock response.
    new_run_id = "run-98765"
    logger.info(f"Job {identifier} restarted successfully. New run ID: {new_run_id}")
    return {"status": "success", "new_run_id": new_run_id, "job_id": job_id}