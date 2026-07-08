"""
Queue configuration and connection management.
Uses Redis Queue (RQ) for async job execution with retry support.
"""
import os

from redis import Redis
from rq import Queue


def get_redis_connection() -> Redis:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url)


def get_job_queue() -> Queue:
    return Queue("orchestrator", connection=get_redis_connection(), default_timeout=1800)
