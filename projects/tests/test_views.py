"""
Тесты вьюшек: доступ, экспорт, log_time, bulk_update, kanban filters.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from projects.models import Project, Task, TimeLog, TaskChangeLog


def make_user(username, role, password='pass'):
    return CustomUser.objects.create_user(
        username=username, password=password, role=role,
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


class AnalyticsViewTests(TestCase):

    def setUp(self):
        self.manager  = make_user('mgr', 'manager')
        self.executor = make_user('exc', 'executor')
        self.client_user = make_user('cli', 'client')
        self.project  = make_project(self.manager)
        self.c = Client()

    def test_analytics_requires_login(self):
        resp = self.c.get(reverse('projects:analytics'))
        self.assertRedirects(resp, '/accounts/login/?next=/analytics/')

    def test_analytics_accessible_by_manager(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(reverse('projects:analytics'))
        self.assertEqual(resp.status_code, 200)

    def test_analytics_forbidden_for_executor(self):
        self.c.login(username='exc', password='pass')
        resp = self.c.get(reverse('projects:analytics'))
        self.assertEqual(resp.status_code, 403)

    def test_analytics_forbidden_for_client(self):
        self.c.login(username='cli', password='pass')
        resp = self.c.get(reverse('projects:analytics'))
        self.assertEqual(resp.status_code, 403)


class ExportViewTests(TestCase):

    def setUp(self):
        self.manager  = make_user('mgr', 'manager')
        self.executor = make_user('exc', 'executor')
        self.project  = make_project(self.manager)
        make_task(self.project, self.manager)
        self.c = Client()

    def test_csv_export_by_manager(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(reverse('projects:export_tasks_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8-sig')

    def test_csv_export_forbidden_for_executor(self):
        self.c.login(username='exc', password='pass')
        resp = self.c.get(reverse('projects:export_tasks_csv'))
        self.assertEqual(resp.status_code, 403)

    def test_csv_contains_task_title(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(reverse('projects:export_tasks_csv'))
        content = resp.content.decode('utf-8-sig')
        self.assertIn('Test Task', content)


class LogTimeViewTests(TestCase):

    def setUp(self):
        self.manager  = make_user('mgr', 'manager')
        self.executor = make_user('exc', 'executor')
        self.client_user = make_user('cli', 'client')
        self.project  = make_project(self.manager)
        self.task = make_task(self.project, self.manager, assignee=self.executor)
        self.c = Client()

    def _log_url(self):
        return reverse('projects:log_time', kwargs={'task_uuid': self.task.uuid})

    def test_log_time_by_manager(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.post(self._log_url(), {'minutes': 60, 'description': 'test'})
        self.assertRedirects(resp, reverse('projects:task_detail', kwargs={'uuid': self.task.uuid}))
        self.assertEqual(TimeLog.objects.filter(task=self.task).count(), 1)

    def test_log_time_by_assigned_executor(self):
        self.c.login(username='exc', password='pass')
        resp = self.c.post(self._log_url(), {'minutes': 30})
        self.assertEqual(TimeLog.objects.filter(task=self.task).count(), 1)

    def test_log_time_forbidden_for_client(self):
        self.c.login(username='cli', password='pass')
        resp = self.c.post(self._log_url(), {'minutes': 30})
        self.assertEqual(resp.status_code, 403)

    def test_log_time_invalid_minutes(self):
        self.c.login(username='mgr', password='pass')
        self.c.post(self._log_url(), {'minutes': 0})
        self.assertEqual(TimeLog.objects.filter(task=self.task).count(), 0)


class BulkTaskUpdateTests(TestCase):

    def setUp(self):
        self.manager  = make_user('mgr', 'manager')
        self.executor = make_user('exc', 'executor')
        self.project  = make_project(self.manager)
        self.task1 = make_task(self.project, self.manager, status='not_started')
        self.task2 = make_task(self.project, self.manager, status='not_started', title='Task 2')
        self.project.executors.add(self.executor)
        self.c = Client()
        self.url = reverse('projects:bulk_task_update')

    def test_bulk_status_change(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.post(self.url, {
            'task_uuids[]': [str(self.task1.uuid), str(self.task2.uuid)],
            'action': 'change_status',
            'value': 'development',
        })
        self.task1.refresh_from_db()
        self.task2.refresh_from_db()
        self.assertEqual(self.task1.status, 'development')
        self.assertEqual(self.task2.status, 'development')

    def test_bulk_creates_changelog(self):
        self.c.login(username='mgr', password='pass')
        self.c.post(self.url, {
            'task_uuids[]': [str(self.task1.uuid)],
            'action': 'change_status',
            'value': 'development',
        })
        self.assertEqual(
            TaskChangeLog.objects.filter(task=self.task1, field_name='Статус').count(), 1
        )

    def test_bulk_forbidden_for_executor(self):
        self.c.login(username='exc', password='pass')
        resp = self.c.post(self.url, {
            'task_uuids[]': [str(self.task1.uuid)],
            'action': 'change_status',
            'value': 'development',
        })
        self.assertEqual(resp.status_code, 403)


class KanbanFiltersTests(TestCase):

    def setUp(self):
        self.manager  = make_user('mgr', 'manager')
        self.executor = make_user('exc', 'executor')
        self.project  = make_project(self.manager)
        self.task_high = make_task(self.project, self.manager, priority='high', title='High Task')
        self.task_low  = make_task(self.project, self.manager, priority='low',  title='Low Task')
        self.c = Client()

    def _board_url(self):
        return reverse('projects:kanban', kwargs={'project_uuid': self.project.uuid})

    def test_kanban_accessible(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(self._board_url())
        self.assertEqual(resp.status_code, 200)

    def test_priority_filter_high(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(self._board_url() + '?priority=high')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['priority_filter'], 'high')

    def test_deadline_filter_overdue(self):
        past = timezone.localdate() - timezone.timedelta(days=2)
        make_task(self.project, self.manager, deadline=past, title='Overdue Task')
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(self._board_url() + '?deadline=overdue')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['deadline_filter'], 'overdue')

    def test_kanban_state_api(self):
        self.c.login(username='mgr', password='pass')
        resp = self.c.get(reverse('projects:kanban_state', kwargs={'project_uuid': self.project.uuid}))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('tasks', data)
        self.assertIn('updated_at', data)
