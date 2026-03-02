import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_taskattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='task',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
