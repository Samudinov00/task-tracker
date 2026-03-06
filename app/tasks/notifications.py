"""
Celery-задача для создания уведомлений (аналог projects/tasks.py).
"""
try:
    from app.celery_app import celery_app

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
    def send_notifications(self, user_ids, task_id, ntype, message):
        """Создаёт уведомления для списка пользователей в фоне."""
        from app.database import SessionLocal
        from app.models.project import Notification, Task

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return
            for user_id in user_ids:
                if user_id:
                    existing = (
                        db.query(Notification)
                        .filter(
                            Notification.user_id == user_id,
                            Notification.task_id == task_id,
                            Notification.notification_type == ntype,
                            Notification.message == message,
                        )
                        .first()
                    )
                    if not existing:
                        notif = Notification(
                            user_id=user_id,
                            task_id=task_id,
                            notification_type=ntype,
                            message=message,
                        )
                        db.add(notif)
            db.commit()
        except Exception as exc:
            db.rollback()
            raise self.retry(exc=exc)
        finally:
            db.close()

except Exception:
    # Celery/Redis недоступен — синхронный fallback
    class _FakeTask:
        @staticmethod
        def delay(*args, **kwargs):
            send_notifications(*args, **kwargs)

    def send_notifications(user_ids, task_id, ntype, message):
        """Синхронный fallback."""
        from app.database import SessionLocal
        from app.models.project import Notification, Task

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return
            for user_id in user_ids:
                if user_id:
                    existing = (
                        db.query(Notification)
                        .filter(
                            Notification.user_id == user_id,
                            Notification.task_id == task_id,
                            Notification.notification_type == ntype,
                            Notification.message == message,
                        )
                        .first()
                    )
                    if not existing:
                        notif = Notification(
                            user_id=user_id,
                            task_id=task_id,
                            notification_type=ntype,
                            message=message,
                        )
                        db.add(notif)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    send_notifications.delay = send_notifications
