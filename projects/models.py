"""
Модели:
  Project        — проект с менеджером, командой и клиентами
  Task           — задача с Канбан-статусом и приоритетом
  Comment        — комментарий к задаче
  Notification   — уведомление для пользователя
  TimeLog        — запись о потраченном времени
  TaskChangeLog  — история изменений полей задачи
"""
import os
import uuid as uuid_lib

from django.db import models
from django.conf import settings
from django.utils import timezone


# ── Проект ────────────────────────────────────────────────────────────────────
class Project(models.Model):
    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
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

    PRIORITY_LOW      = 'low'
    PRIORITY_MEDIUM   = 'medium'
    PRIORITY_HIGH     = 'high'
    PRIORITY_CRITICAL = 'critical'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW,      'Низкий'),
        (PRIORITY_MEDIUM,   'Средний'),
        (PRIORITY_HIGH,     'Высокий'),
        (PRIORITY_CRITICAL, 'Критический'),
    ]

    PRIORITY_BADGE = {
        PRIORITY_LOW:      'success',
        PRIORITY_MEDIUM:   'warning',
        PRIORITY_HIGH:     'orange',
        PRIORITY_CRITICAL: 'danger',
    }

    PRIORITY_ICON = {
        PRIORITY_LOW:      'bi-arrow-down',
        PRIORITY_MEDIUM:   'bi-dash',
        PRIORITY_HIGH:     'bi-arrow-up',
        PRIORITY_CRITICAL: 'bi-exclamation-triangle-fill',
    }

    uuid        = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
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
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM, verbose_name='Приоритет',
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
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['deadline']),
            models.Index(fields=['order']),
            models.Index(fields=['project', 'status'], name='task_project_status_idx'),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._save_originals()

    def _save_originals(self):
        self._original_title       = self.title
        self._original_description = self.description
        self._original_assignee_id = self.assignee_id
        self._original_deadline    = self.deadline
        self._original_priority    = self.priority

    def save(self, *args, **kwargs):
        changed_by = getattr(self, '_changed_by', None)
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not is_new and changed_by:
            self._create_change_logs(changed_by)
        self._save_originals()

    def _create_change_logs(self, changed_by):
        tracked = [
            ('title',       'Название',    self._original_title,                self.title),
            ('description', 'Описание',    self._original_description,          self.description),
            ('assignee_id', 'Исполнитель', str(self._original_assignee_id or ''), str(self.assignee_id or '')),
            ('deadline',    'Дедлайн',     str(self._original_deadline or ''),  str(self.deadline or '')),
            ('priority',    'Приоритет',   self._original_priority,             self.priority),
        ]
        for _field_key, field_name, old_val, new_val in tracked:
            if old_val != new_val:
                TaskChangeLog.objects.create(
                    task=self,
                    changed_by=changed_by,
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                )

    def __str__(self):
        return self.title

    def get_status_badge(self):
        return self.STATUS_BADGE.get(self.status, 'secondary')

    def get_priority_badge(self):
        return self.PRIORITY_BADGE.get(self.priority, 'secondary')

    def get_priority_icon(self):
        return self.PRIORITY_ICON.get(self.priority, 'bi-dash')

    def is_overdue(self):
        if self.deadline and self.status != self.STATUS_PRODUCTION:
            return self.deadline < timezone.localdate()
        return False

    def get_total_logged_minutes(self):
        return self.time_logs.aggregate(total=models.Sum('minutes'))['total'] or 0


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
        indexes = [
            models.Index(fields=['-changed_at']),
        ]

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
        indexes = [
            models.Index(fields=['is_read']),
            models.Index(fields=['-created_at']),
        ]

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


# ── Трекер времени ────────────────────────────────────────────────────────────
class TimeLog(models.Model):
    task        = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_logs', verbose_name='Задача')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    minutes     = models.PositiveIntegerField(verbose_name='Минуты')
    description = models.TextField(blank=True, verbose_name='Описание')
    logged_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Лог времени'
        verbose_name_plural = 'Логи времени'
        ordering = ['-logged_at']

    def __str__(self):
        return f'{self.user} — {self.minutes} мин. → {self.task}'


# ── История изменений задачи ──────────────────────────────────────────────────
class TaskChangeLog(models.Model):
    task       = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='change_logs', verbose_name='Задача')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Кто изменил')
    field_name = models.CharField(max_length=100, verbose_name='Поле')
    old_value  = models.TextField(blank=True, verbose_name='Старое значение')
    new_value  = models.TextField(blank=True, verbose_name='Новое значение')
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name='Время изменения')

    class Meta:
        verbose_name = 'Лог изменений'
        verbose_name_plural = 'Логи изменений'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['task', '-changed_at']),
        ]

    def __str__(self):
        return f'{self.task} — {self.field_name}'
