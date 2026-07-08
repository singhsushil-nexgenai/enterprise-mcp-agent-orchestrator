from threading import Lock
from typing import Dict, Optional

from app.models import JobRecord, JobStatus, now_utc


class InMemoryJobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: Dict[str, JobRecord] = {}

    def create(self, record: JobRecord) -> JobRecord:
        with self._lock:
            self._jobs[record.job_id] = record
            return record

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(self, job_id: str, status: JobStatus, message: str = "") -> Optional[JobRecord]:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return None
            updated = current.model_copy(
                update={
                    "status": status,
                    "message": message or current.message,
                    "updated_at": now_utc(),
                }
            )
            self._jobs[job_id] = updated
            return updated

    def set_artifact(self, job_id: str, artifact_url: str) -> Optional[JobRecord]:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return None
            updated = current.model_copy(
                update={
                    "artifact_url": artifact_url,
                    "updated_at": now_utc(),
                }
            )
            self._jobs[job_id] = updated
            return updated
