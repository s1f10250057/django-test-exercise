import django.db.models.deletion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


LEGACY_OWNER_USERNAME = 'legacy-task-owner'


def backfill_task_owner(apps, schema_editor):
    Task = apps.get_model('todo', 'Task')
    database = schema_editor.connection.alias
    ownerless_tasks = Task.objects.using(database).filter(owner__isnull=True)
    if not ownerless_tasks.exists():
        return

    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    username_field = get_user_model().USERNAME_FIELD
    username = LEGACY_OWNER_USERNAME
    suffix = 1
    while User.objects.using(database).filter(**{username_field: username}).exists():
        username = '{}-{}'.format(LEGACY_OWNER_USERNAME, suffix)
        suffix += 1

    user_fields = {field.name for field in User._meta.fields}
    user_values = {
        username_field: username,
        'password': make_password(None),
    }
    if 'email' in user_fields:
        user_values['email'] = ''
    if 'is_active' in user_fields:
        user_values['is_active'] = False

    legacy_owner = User.objects.using(database).create(**user_values)
    ownerless_tasks.update(owner_id=legacy_owner.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('todo', '0005_task_owner'),
    ]

    operations = [
        migrations.RunPython(backfill_task_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='task',
            name='owner',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tasks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
