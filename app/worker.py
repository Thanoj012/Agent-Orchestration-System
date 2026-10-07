"""Celery worker: executes runs off the request path.

Start with:  celery -A app.worker.celery_app worker --loglevel=info
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("orchestrai", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,             # a crashed worker's task is redelivered...
    worker_prefetch_multiplier=1,    # ...and long runs don't starve each other
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="orchestrai.advance_run")
def advance_run_task(run_id: str) -> str:
    """Start a queued run or resume one after a human decision. Idempotent: state lives in PostgreSQL."""
    from app.container import get_container  # heavy imports happen inside the worker only
    from app.orchestration.runner import advance_run

    c = get_container()
    return advance_run(run_id, session_factory=c.session_factory, graph=c.graph, emit=c.emit)
