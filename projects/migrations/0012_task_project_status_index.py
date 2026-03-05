from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0011_priority_timelog_changelog'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['project', 'status'], name='task_project_status_idx'),
        ),
    ]
