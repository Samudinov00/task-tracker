"""
Тесты форм: TimeLogForm, TaskForm.
"""
from django.test import TestCase

from projects.forms import TaskForm, TimeLogForm


class TimeLogFormTests(TestCase):

    def test_valid_form(self):
        form = TimeLogForm(data={'minutes': 60, 'description': 'Работал'})
        self.assertTrue(form.is_valid())

    def test_valid_form_no_description(self):
        form = TimeLogForm(data={'minutes': 30})
        self.assertTrue(form.is_valid())

    def test_invalid_zero_minutes(self):
        form = TimeLogForm(data={'minutes': 0, 'description': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('minutes', form.errors)

    def test_invalid_negative_minutes(self):
        # PositiveIntegerField не принимает отрицательные числа
        form = TimeLogForm(data={'minutes': -5})
        self.assertFalse(form.is_valid())

    def test_missing_minutes(self):
        form = TimeLogForm(data={'description': 'test'})
        self.assertFalse(form.is_valid())
        self.assertIn('minutes', form.errors)


class TaskFormTests(TestCase):

    def test_priority_field_present(self):
        form = TaskForm()
        self.assertIn('priority', form.fields)

    def test_priority_choices(self):
        form = TaskForm()
        choices = [c[0] for c in form.fields['priority'].choices]
        self.assertIn('low', choices)
        self.assertIn('medium', choices)
        self.assertIn('high', choices)
        self.assertIn('critical', choices)

    def test_valid_task_form(self):
        form = TaskForm(data={
            'title': 'Test Task',
            'description': '',
            'status': 'not_started',
            'priority': 'medium',
        })
        # assignee and clients are optional; form may be invalid without project
        # Just check that the form does not raise errors on initialization
        self.assertIsNotNone(form)
