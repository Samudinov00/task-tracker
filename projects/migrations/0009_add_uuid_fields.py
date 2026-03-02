import uuid

from django.db import migrations, models


def populate_uuids(apps, schema_editor):
    """Генерируем уникальный UUID для каждой существующей строки."""
    Project = apps.get_model('projects', 'Project')
    for row in Project.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])

    Task = apps.get_model('projects', 'Task')
    for row in Task.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_taskattachment'),
    ]

    operations = [
        # Шаг 1: добавить поля без уникального ограничения, допуская NULL
        migrations.AddField(
            model_name='project',
            name='uuid',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name='task',
            name='uuid',
            field=models.UUIDField(null=True, editable=False),
        ),
        # Шаг 2: заполнить уникальными UUID каждую строку
        migrations.RunPython(populate_uuids, migrations.RunPython.noop),
        # Шаг 3: сделать поля обязательными и уникальными
        migrations.AlterField(
            model_name='project',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
