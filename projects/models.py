"""
Модели:
  Project      — проект с менеджером, командой и клиентами
  Task         — задача с Канбан-статусом
  Comment      — комментарий к задаче
  Notification — уведомление для пользователя
"""
import os

from django.db import models
from django.conf import settings
from django.utils import timezone


# ── Проект ────────────────────────────────────────────────────────────────────
class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_projects',
        verbose_name='Менеджер',
    )
    # Исполнители, работающие над проектом
    executors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='executor_projects',
        verbose_name='Исполнители',
    )
    # Клиенты, которым виден проект
    clients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='client_projects',
        verbose_name='Клиенты',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_progress(self):
        """Процент выполненных задач."""
        total = self.tasks.count()
        if total == 0:
            return 0
        done = self.tasks.filter(status='production').count()
        return int(done / total * 100)


# ── Задача ────────────────────────────────────────────────────────────────────
class Task(models.Model):
    STATUS_NOT_STARTED   = 'not_started'
    STATUS_DEVELOPMENT   = 'development'
    STATUS_TEST_NSK      = 'test_nsk'
    STATUS_TEST_DISTRICT = 'test_district'
    STATUS_PRODUCTION    = 'production'

    STATUS_CHOICES = [
        (STATUS_NOT_STARTED,   'Не начата'),
        (STATUS_DEVELOPMENT,   'Разработка'),
        (STATUS_TEST_NSK,      'Тест НСК'),
        (STATUS_TEST_DISTRICT, 'Тест район'),
        (STATUS_PRODUCTION,    'Промышленная эксплуатация'),
    ]

    STATUS_BADGE = {
        STATUS_NOT_STARTED:   'secondary',
        STATUS_DEVELOPMENT:   'primary',
        STATUS_TEST_NSK:      'warning',
        STATUS_TEST_DISTRICT: 'warning',
        STATUS_PRODUCTION:    'success',
    }

    title       = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    project     = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='tasks', verbose_name='Проект',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default=STATUS_NOT_STARTED, verbose_name='Статус',
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks', verbose_name='Исполнитель',
    )
    clients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='client_tasks', verbose_name='Клиенты',
    )
    deadline = models.DateField(null=True, blank=True, verbose_name='Дедлайн')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tasks', verbose_name='Создал',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    # Порядок внутри Канбан-колонки
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    def get_status_badge(self):
        return self.STATUS_BADGE.get(self.status, 'secondary')

    def is_overdue(self):
        if self.deadline and self.status != self.STATUS_PRODUCTION:
            return self.deadline < timezone.localdate()
        return False


# ── Лог смены статусов ────────────────────────────────────────────────────────
class TaskStatusLog(models.Model):
    task       = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='status_logs', verbose_name='Задача')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='status_changes', verbose_name='Кто изменил')
    old_status = models.CharField(max_length=20, verbose_name='Старый статус')
    new_status = models.CharField(max_length=20, verbose_name='Новый статус')
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name='Время изменения')

    class Meta:
        verbose_name = 'Лог статуса'
        verbose_name_plural = 'Логи статусов'
        ordering = ['-changed_at']

    def get_old_status_display(self):
        return dict(Task.STATUS_CHOICES).get(self.old_status, self.old_status)

    def get_new_status_display(self):
        return dict(Task.STATUS_CHOICES).get(self.new_status, self.new_status)


# ── Комментарий ───────────────────────────────────────────────────────────────
class Comment(models.Model):
    task   = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='comments', verbose_name='Задача',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name='Автор',
    )
    text       = models.TextField(verbose_name='Текст')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f'Комментарий {self.author} → {self.task}'


# ── Уведомления ───────────────────────────────────────────────────────────────
class Notification(models.Model):
    TYPE_TASK_ASSIGNED = 'task_assigned'
    TYPE_TASK_STATUS   = 'task_status'
    TYPE_COMMENT       = 'comment'

    TYPE_CHOICES = [
        (TYPE_TASK_ASSIGNED, 'Назначена задача'),
        (TYPE_TASK_STATUS,   'Изменён статус'),
        (TYPE_COMMENT,       'Новый комментарий'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Пользователь',
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        null=True, blank=True, verbose_name='Задача',
    )
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES,
        default=TYPE_COMMENT, verbose_name='Тип',
    )
    message    = models.CharField(max_length=500, verbose_name='Сообщение')
    is_read    = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return self.message


# ── Вложения к задаче ─────────────────────────────────────────────────────────
class TaskAttachment(models.Model):
    task        = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file        = models.FileField(upload_to='task_attachments/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def filename(self):
        return os.path.basename(self.file.name)
