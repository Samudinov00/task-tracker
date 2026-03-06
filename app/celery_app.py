"""
Celery-приложение (аналог task_tracker/celery.py в Django).
"""
from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, TIMEZONE

celery_app = Celery(
    "task_tracker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks.notifications"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=TIMEZONE,
    enable_utc=True,
    task_track_started=True,
)
