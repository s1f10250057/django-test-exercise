from django.db import migrations, models


def migrate_completed_to_status(apps, schema_editor):
    task_model = apps.get_model('todo', 'Task')
    task_model.objects.filter(completed=True).update(status='done')


def restore_completed_from_status(apps, schema_editor):
    task_model = apps.get_model('todo', 'Task')
    task_model.objects.filter(status='done').update(completed=True)


class Migration(migrations.Migration):
    dependencies = [
        ('todo', '0005_task_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='category',
            field=models.CharField(
                choices=[
                    ('university', '大学'),
                    ('personal', '個人'),
                    ('part_time', 'アルバイト'),
                    ('other', 'その他'),
                ],
                default='other',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='priority',
            field=models.CharField(
                choices=[('high', '高'), ('medium', '中'), ('low', '低')],
                default='medium',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='status',
            field=models.CharField(
                choices=[
                    ('todo', '未着手'),
                    ('doing', '進行中'),
                    ('done', '完了'),
                ],
                default='todo',
                max_length=10,
            ),
        ),
        migrations.RunPython(
            migrate_completed_to_status,
            restore_completed_from_status,
        ),
        migrations.RemoveField(
            model_name='task',
            name='completed',
        ),
    ]
