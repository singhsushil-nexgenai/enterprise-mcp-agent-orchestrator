"""
Database-backed job store replacing the in-memory implementation.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import JobTable, AuditEventTable
from app.models import JobStatus, JobRecord


def _to_record(row: JobTable) -> JobRecord:
    return JobRecord(
        job_id=row.job_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        requested_job_name=row.requested_job_name,
        requested_table_name=row.requested_table_name,
        repo=row.repo,
        message=row.message,
        artifact_url=row.artifact_url,
    )


def create_job(db: Session, record: JobRecord) -> JobRecord:
    row = JobTable(
        job_id=record.job_id,
        status=record.status,
        requested_job_name=record.requested_job_name,
        requested_table_name=record.requested_table_name,
        repo=record.repo,
        message=record.message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _audit(db, row.job_id, "job_created", record.message)
    return _to_record(row)


def get_job(db: Session, job_id: str) -> Optional[JobRecord]:
    row = db.get(JobTable, job_id)
    if row is None:
        return None
    return _to_record(row)


def list_jobs(db: Session, limit: int = 50, offset: int = 0) -> list[JobRecord]:
    rows = db.query(JobTable).order_by(JobTable.created_at.desc()).offset(offset).limit(limit).all()
    return [_to_record(r) for r in rows]


def update_status(db: Session, job_id: str, status: JobStatus, message: str = "") -> Optional[JobRecord]:
    row = db.get(JobTable, job_id)
    if row is None:
        return None
    row.status = status
    if message:
        row.message = message
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    _audit(db, job_id, f"status_changed_to_{status.value}", message)
    return _to_record(row)


def set_artifact(db: Session, job_id: str, artifact_url: str) -> Optional[JobRecord]:
    row = db.get(JobTable, job_id)
    if row is None:
        return None
    row.artifact_url = artifact_url
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    _audit(db, job_id, "artifact_published", artifact_url)
    return _to_record(row)


def increment_retry(db: Session, job_id: str) -> None:
    row = db.get(JobTable, job_id)
    if row:
        row.retry_count = (row.retry_count or 0) + 1
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        _audit(db, job_id, "retry_attempt", f"retry #{row.retry_count}")


def get_audit_trail(db: Session, job_id: str) -> list[dict]:
    rows = db.query(AuditEventTable).filter_by(job_id=job_id).order_by(AuditEventTable.timestamp.asc()).all()
    return [
        {"id": r.id, "job_id": r.job_id, "event_type": r.event_type, "detail": r.detail, "actor": r.actor, "timestamp": r.timestamp.isoformat()}
        for r in rows
    ]


def _audit(db: Session, job_id: str, event_type: str, detail: str = "", actor: str = "system") -> None:
    event = AuditEventTable(job_id=job_id, event_type=event_type, detail=detail, actor=actor)
    db.add(event)
    db.commit()
