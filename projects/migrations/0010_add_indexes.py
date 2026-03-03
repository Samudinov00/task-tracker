from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0009_add_uuid_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['status'], name='projects_ta_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['created_at'], name='projects_ta_created_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['deadline'], name='projects_ta_deadline_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['order'], name='projects_ta_order_idx'),
        ),
        migrations.AddIndex(
            model_name='taskstatuslog',
            index=models.Index(fields=['-changed_at'], name='projects_tsl_changed_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['is_read'], name='projects_notif_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['-created_at'], name='projects_notif_created_idx'),
        ),
    ]
