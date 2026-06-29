from celery import Celery

from app.config import settings

celery_app = Celery(
    "railway",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.tasks.worker_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,
    task_soft_time_limit=3300,
)
