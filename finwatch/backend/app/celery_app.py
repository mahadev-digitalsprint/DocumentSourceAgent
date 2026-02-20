"""Celery application instance."""
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "finwatch",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_concurrency,
    task_routes={
        "app.tasks.run_pipeline": {"queue": "default"},
        "app.tasks.run_daily_digest": {"queue": "default"},
    },
)
