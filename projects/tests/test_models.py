"""
Тесты моделей: Task, TimeLog, TaskChangeLog.
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from projects.models import Project, Task, TaskChangeLog, TimeLog


def make_manager(username='manager1'):
    return CustomUser.objects.create_user(
        username=username, password='pass', role='manager',
        email=f'{username}@test.com',
    )


def make_executor(username='executor1'):
    return CustomUser.objects.create_user(
        username=username, password='pass', role='executor',
        email=f'{username}@test.com',
    )


def make_project(manager):
    return Project.objects.create(name='Test Project', manager=manager)


def make_task(project, created_by, **kwargs):
    kwargs.setdefault('title', 'Test Task')
    return Task.objects.create(
        project=project,
        created_by=created_by,
        **kwargs,
    )


class TaskModelTests(TestCase):

    def setUp(self):
        self.manager  = make_manager()
        self.project  = make_project(self.manager)

    def test_is_overdue_no_deadline(self):
        task = make_task(self.project, self.manager)
        self.assertFalse(task.is_overdue())

    def test_is_overdue_future_deadline(self):
        future = timezone.localdate() + timezone.timedelta(days=5)
        task = make_task(self.project, self.manager, deadline=future)
        self.assertFalse(task.is_overdue())

    def test_is_overdue_past_deadline(self):
        past = timezone.localdate() - timezone.timedelta(days=1)
        task = make_task(self.project, self.manager, deadline=past)
        self.assertTrue(task.is_overdue())

    def test_is_overdue_production_not_overdue(self):
        past = timezone.localdate() - timezone.timedelta(days=1)
        task = make_task(self.project, self.manager, deadline=past, status=Task.STATUS_PRODUCTION)
        self.assertFalse(task.is_overdue())

    def test_get_status_badge_default(self):
        task = make_task(self.project, self.manager)
        self.assertEqual(task.get_status_badge(), 'secondary')

    def test_get_status_badge_production(self):
        task = make_task(self.project, self.manager, status=Task.STATUS_PRODUCTION)
        self.assertEqual(task.get_status_badge(), 'success')

    def test_default_priority_is_medium(self):
        task = make_task(self.project, self.manager)
        self.assertEqual(task.priority, Task.PRIORITY_MEDIUM)

    def test_get_priority_badge(self):
        task = make_task(self.project, self.manager, priority=Task.PRIORITY_CRITICAL)
        self.assertEqual(task.get_priority_badge(), 'danger')

    def test_get_total_logged_minutes_no_logs(self):
        task = make_task(self.project, self.manager)
        self.assertEqual(task.get_total_logged_minutes(), 0)

    def test_str(self):
        task = make_task(self.project, self.manager, title='My Task')
        self.assertEqual(str(task), 'My Task')


class TimeLogModelTests(TestCase):

    def setUp(self):
        self.manager  = make_manager()
        self.executor = make_executor()
        self.project  = make_project(self.manager)
        self.task     = make_task(self.project, self.manager, assignee=self.executor)

    def test_create_timelog(self):
        log = TimeLog.objects.create(task=self.task, user=self.executor, minutes=90, description='Работал')
        self.assertEqual(log.minutes, 90)
        self.assertEqual(log.task, self.task)

    def test_total_logged_minutes(self):
        TimeLog.objects.create(task=self.task, user=self.executor, minutes=60)
        TimeLog.objects.create(task=self.task, user=self.manager, minutes=30)
        self.assertEqual(self.task.get_total_logged_minutes(), 90)

    def test_str(self):
        log = TimeLog.objects.create(task=self.task, user=self.executor, minutes=45)
        self.assertIn('45', str(log))


class TaskChangeLogTests(TestCase):

    def setUp(self):
        self.manager  = make_manager()
        self.project  = make_project(self.manager)
        self.task     = make_task(self.project, self.manager, title='Original Title')

    def test_change_tracking_title(self):
        self.task._changed_by = self.manager
        self.task.title = 'New Title'
        self.task.save()

        logs = TaskChangeLog.objects.filter(task=self.task, field_name='Название')
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.old_value, 'Original Title')
        self.assertEqual(log.new_value, 'New Title')
        self.assertEqual(log.changed_by, self.manager)

    def test_change_tracking_priority(self):
        self.task._changed_by = self.manager
        self.task.priority = Task.PRIORITY_CRITICAL
        self.task.save()

        logs = TaskChangeLog.objects.filter(task=self.task, field_name='Приоритет')
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().new_value, Task.PRIORITY_CRITICAL)

    def test_no_change_log_when_nothing_changed(self):
        self.task._changed_by = self.manager
        self.task.save()  # nothing changed

        count = TaskChangeLog.objects.filter(task=self.task).count()
        self.assertEqual(count, 0)

    def test_no_change_log_for_new_task(self):
        """Новые задачи не создают логи изменений."""
        count = TaskChangeLog.objects.filter(task=self.task).count()
        self.assertEqual(count, 0)

    def test_no_change_log_without_changed_by(self):
        """Если _changed_by не установлен, логи не создаются."""
        self.task.title = 'Another Title'
        self.task.save()

        count = TaskChangeLog.objects.filter(task=self.task).count()
        self.assertEqual(count, 0)
