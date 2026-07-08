"""
Retry policy configuration for the enterprise orchestrator queue.

Retry semantics:
- Exponential backoff: base_delay * 2^(attempt - 1)
- Max attempts: 4 (1 initial + 3 retries)
- Base delay: 30 seconds
- Max delay cap: 300 seconds (5 minutes)
- Dead-letter after all retries exhausted
"""
import os

MAX_RETRIES = int(os.getenv("JOB_MAX_RETRIES", "3"))
BASE_DELAY_SECONDS = int(os.getenv("JOB_RETRY_BASE_DELAY", "30"))
MAX_DELAY_SECONDS = int(os.getenv("JOB_RETRY_MAX_DELAY", "300"))
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT", "1800"))


def get_retry_intervals() -> list[int]:
    """Return list of retry intervals in seconds using exponential backoff."""
    intervals = []
    for attempt in range(MAX_RETRIES):
        delay = min(BASE_DELAY_SECONDS * (2 ** attempt), MAX_DELAY_SECONDS)
        intervals.append(delay)
    return intervals
