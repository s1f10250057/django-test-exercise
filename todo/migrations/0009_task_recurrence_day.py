from django.db import migrations, models


def backfill_recurrence_day(apps, schema_editor):
    Task = apps.get_model('todo', 'Task')
    monthly_tasks = Task.objects.filter(
        recurrence='monthly',
        due_at__isnull=False,
    )
    for task in monthly_tasks.iterator():
        task.recurrence_day = task.due_at.day
        task.save(update_fields=['recurrence_day'])


class Migration(migrations.Migration):

    dependencies = [
    ('todo', '0008_task_recurrence_source'),
]

    operations = [
        migrations.AddField(
            model_name='task',
            name='recurrence_day',
            field=models.PositiveSmallIntegerField(
                blank=True,
                editable=False,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_recurrence_day,
            migrations.RunPython.noop,
        ),
    ]
