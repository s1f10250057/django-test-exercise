import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('todo', '0007_merge_20260716_1543'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='recurrence_source',
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='next_occurrence',
                to='todo.task',
            ),
        ),
    ]
