"""
Кастомная модель пользователя с тремя ролями:
  - manager  — полный доступ, управляет проектами и командой
  - executor — видит/исполняет свои задачи
  - client   — читает прогресс своих проектов, комментирует
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_MANAGER = 'manager'
    ROLE_EXECUTOR = 'executor'
    ROLE_CLIENT = 'client'

    ROLE_CHOICES = [
        (ROLE_MANAGER, 'Менеджер'),
        (ROLE_EXECUTOR, 'Исполнитель'),
        (ROLE_CLIENT, 'Клиент'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_EXECUTOR,
        verbose_name='Роль',
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='Аватар',
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    # --- Хелперы для проверки роли ---
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    def is_executor(self):
        return self.role == self.ROLE_EXECUTOR

    def is_client(self):
        return self.role == self.ROLE_CLIENT

    def get_initials(self):
        """Инициалы для аватара-заглушки."""
        if self.first_name and self.last_name:
            return f'{self.first_name[0]}{self.last_name[0]}'.upper()
        return self.username[:2].upper()

    def get_display_name(self):
        return self.get_full_name() or self.username
