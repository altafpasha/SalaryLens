"""
SalaryLens AI by CodeSec — Celery Application
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "salarylens",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    include=["app.workers.tasks"],
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes maximum runtime per task
    task_soft_time_limit=240,
)
