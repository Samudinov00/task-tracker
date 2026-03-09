"""
Celery Beat задача: ежедневные напоминания о дедлайнах.
Запускается каждый день в 09:00 по часовому поясу проекта.
"""
from datetime import date, timedelta

try:
    from app.celery_app import celery_app

    @celery_app.task
    def send_deadline_reminders():
        """Отправляет Telegram-уведомления о задачах с дедлайном сегодня или завтра."""
        from app.database import SessionLocal
        from app.models.project import Task
        from app.models.user import User
        from app import telegram

        db = SessionLocal()
        try:
            today    = date.today()
            tomorrow = today + timedelta(days=1)

            tasks = (
                db.query(Task)
                .filter(Task.deadline.in_([today, tomorrow]))
                .all()
            )

            for task in tasks:
                # Пропускаем завершённые задачи
                if task.status_obj and task.status_obj.is_final:
                    continue
                if not task.assignee_id:
                    continue

                assignee = db.query(User).filter(User.id == task.assignee_id).first()
                if not assignee or not assignee.telegram_id:
                    continue

                deadline_label = (
                    "сегодня"  if task.deadline == today else "завтра"
                )
                deadline_str = f"{task.deadline.strftime('%d.%m.%Y')} ({deadline_label})"
                project_name = task.project.name if task.project else "—"

                telegram.notify_deadline_reminder(
                    telegram_id=assignee.telegram_id,
                    task_title=task.title,
                    project_name=project_name,
                    deadline_str=deadline_str,
                    task_uuid=str(task.uuid),
                )
        finally:
            db.close()

except Exception:
    def send_deadline_reminders():
        pass
    send_deadline_reminders.delay = send_deadline_reminders
