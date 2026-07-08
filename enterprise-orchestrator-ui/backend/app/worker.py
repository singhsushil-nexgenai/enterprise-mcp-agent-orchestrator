"""
RQ Worker entry point.

Usage:
    cd enterprise-orchestrator-ui/backend
    python -m app.worker

Or via rq CLI:
    rq worker orchestrator --url redis://localhost:6379/0
"""
import os
import sys
import platform
import logging

from dotenv import load_dotenv
from redis import Redis
from rq import Queue
from rq.worker import SimpleWorker, Worker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    conn = Redis.from_url(redis_url)
    queues = [Queue("orchestrator", connection=conn)]

    # Windows lacks os.fork(); use SimpleWorker which runs in-process.
    WorkerClass = SimpleWorker if platform.system() == "Windows" else Worker
    worker = WorkerClass(queues, connection=conn)
    logging.info("Starting RQ worker on queue 'orchestrator' (redis=%s)", redis_url)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    # Ensure the project root is on sys.path so `app.*` imports resolve.
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    main()
