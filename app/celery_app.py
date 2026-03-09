"""
Celery-приложение (аналог task_tracker/celery.py в Django).
"""
from celery import Celery

from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, TIMEZONE

celery_app = Celery(
    "task_tracker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks.notifications", "app.tasks.deadline_reminders"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "deadline-reminders-daily": {
            "task": "app.tasks.deadline_reminders.send_deadline_reminders",
            "schedule": 86400,  # раз в сутки
        },
    },
)
