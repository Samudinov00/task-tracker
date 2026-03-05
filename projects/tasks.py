from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_notifications(self, user_ids, task_id, ntype, message):
    """Создаёт уведомления для списка пользователей в фоне."""
    from .models import Notification, Task
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return

    for user_id in user_ids:
        if user_id:
            Notification.objects.get_or_create(
                user_id=user_id,
                task=task,
                notification_type=ntype,
                message=message,
            )
