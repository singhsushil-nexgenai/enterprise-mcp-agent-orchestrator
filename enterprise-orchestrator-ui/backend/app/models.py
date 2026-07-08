from enum import Enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    SUBMITTED = "submitted"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreateRequest(BaseModel):
    job_name: Optional[str] = None
    table_name: Optional[str] = None
    repo: Optional[str] = Field(default=None, description="cmpgn | uma | rvnu")
    publish_to_sharepoint: bool = True
    publish_to_confluence: bool = False


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    requested_job_name: Optional[str] = None
    requested_table_name: Optional[str] = None
    repo: Optional[str] = None
    message: str = ""
    artifact_url: Optional[str] = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
