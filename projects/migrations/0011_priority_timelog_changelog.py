import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_add_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Добавить поле priority в Task
        migrations.AddField(
            model_name='task',
            name='priority',
            field=models.CharField(
                choices=[
                    ('low', 'Низкий'),
                    ('medium', 'Средний'),
                    ('high', 'Высокий'),
                    ('critical', 'Критический'),
                ],
                default='medium',
                max_length=20,
                verbose_name='Приоритет',
            ),
        ),

        # Создать модель TimeLog
        migrations.CreateModel(
            name='TimeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('minutes', models.PositiveIntegerField(verbose_name='Минуты')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='time_logs',
                    to='projects.task',
                    verbose_name='Задача',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь',
                )),
            ],
            options={
                'verbose_name': 'Лог времени',
                'verbose_name_plural': 'Логи времени',
                'ordering': ['-logged_at'],
            },
        ),

        # Создать модель TaskChangeLog
        migrations.CreateModel(
            name='TaskChangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=100, verbose_name='Поле')),
                ('old_value', models.TextField(blank=True, verbose_name='Старое значение')),
                ('new_value', models.TextField(blank=True, verbose_name='Новое значение')),
                ('changed_at', models.DateTimeField(auto_now_add=True, verbose_name='Время изменения')),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='change_logs',
                    to='projects.task',
                    verbose_name='Задача',
                )),
                ('changed_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Кто изменил',
                )),
            ],
            options={
                'verbose_name': 'Лог изменений',
                'verbose_name_plural': 'Логи изменений',
                'ordering': ['-changed_at'],
            },
        ),

        # Индекс для TaskChangeLog
        migrations.AddIndex(
            model_name='taskchangelog',
            index=models.Index(fields=['task', '-changed_at'], name='projects_tcl_task_changed_idx'),
        ),
    ]
