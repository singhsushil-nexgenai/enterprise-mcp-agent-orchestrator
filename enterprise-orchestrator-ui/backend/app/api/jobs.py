from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from rq import Retry

from app.models import JobCreateRequest, JobRecord, JobStatus, now_utc
from app.database import get_db
from app.services import db_store
from app.services.queue import get_job_queue
from app.services.retry_policy import get_retry_intervals, JOB_TIMEOUT_SECONDS

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRecord, status_code=201)
def submit_job(payload: JobCreateRequest, db: Session = Depends(get_db)) -> JobRecord:
    if not payload.job_name and not payload.table_name:
        raise HTTPException(status_code=400, detail="Either job_name or table_name is required")

    job_id = str(uuid4())
    record = JobRecord(
        job_id=job_id,
        status=JobStatus.SUBMITTED,
        created_at=now_utc(),
        updated_at=now_utc(),
        requested_job_name=payload.job_name,
        requested_table_name=payload.table_name,
        repo=payload.repo,
        message="Job submitted — queued for execution",
    )
    db_store.create_job(db, record)

    # Enqueue to Redis with retry policy
    queue = get_job_queue()
    retry_intervals = get_retry_intervals()
    queue.enqueue(
        "app.workers.runner.execute_orchestration",
        job_id,
        payload.job_name,
        payload.table_name,
        payload.repo,
        job_timeout=JOB_TIMEOUT_SECONDS,
        retry=Retry(max=len(retry_intervals), interval=retry_intervals),
        job_id=f"orch-{job_id}",
    )

    db_store.update_status(db, job_id, JobStatus.QUEUED, "Enqueued to worker queue")
    return db_store.get_job(db, job_id)  # type: ignore[return-value]


@router.get("", response_model=list[JobRecord])
def list_jobs(limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> list[JobRecord]:
    return db_store.list_jobs(db, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobRecord:
    record = db_store.get_job(db, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return record


@router.post("/{job_id}/cancel", response_model=JobRecord)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> JobRecord:
    record = db_store.get_job(db, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a job in '{record.status.value}' state")
    updated = db_store.update_status(db, job_id, JobStatus.FAILED, "Cancelled by user")
    return updated  # type: ignore[return-value]


@router.get("/{job_id}/audit")
def get_audit_trail(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    record = db_store.get_job(db, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_store.get_audit_trail(db, job_id)
