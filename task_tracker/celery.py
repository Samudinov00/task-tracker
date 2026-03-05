import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'task_tracker.settings')

app = Celery('task_tracker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
