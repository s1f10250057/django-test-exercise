from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from todo.models import Task


class TaskOwnerMigrationTestCase(TransactionTestCase):
    migrate_from = [('todo', '0005_task_owner')]
    migrate_to = [('todo', '0010_task_description')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.addCleanup(self.migrate_to_latest)

        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldTask = old_apps.get_model('todo', 'Task')
        OldUser = old_apps.get_model('auth', 'User')
        existing_user = OldUser.objects.create(
            username='legacy-task-owner',
            password='!',
            is_active=True,
        )
        self.existing_user_id = existing_user.pk
        self.task_id = OldTask.objects.create(title='legacy task').pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)

    def migrate_to_latest(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_ownerless_task_is_backfilled_and_can_be_reassigned(self):
        task = Task.objects.select_related('owner').get(pk=self.task_id)

        self.assertIsNotNone(task.owner_id)
        self.assertNotEqual(task.owner_id, self.existing_user_id)
        self.assertTrue(task.owner.username.startswith('legacy-task-owner-'))
        self.assertFalse(task.owner.is_active)
        self.assertFalse(task.owner.has_usable_password())
        self.assertFalse(Task._meta.get_field('owner').null)

        owner = get_user_model().objects.create_user(username='owner', password='password')
        task.owner = owner
        task.save(update_fields=['owner'])
        self.client.force_login(owner)

        response = self.client.post(reverse('complete', args=[task.pk]))

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)


class MonthlyRecurrenceMigrationTestCase(TransactionTestCase):
    migrate_from = [('todo', '0008_task_recurrence_source')]
    migrate_to = [('todo', '0010_task_description')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.addCleanup(self.migrate_to_latest)

        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldTask = old_apps.get_model('todo', 'Task')
        OldUser = old_apps.get_model('auth', 'User')
        owner = OldUser.objects.create(
            username='monthly-owner',
            password='!',
        )
        self.task_id = OldTask.objects.create(
            owner_id=owner.pk,
            title='legacy monthly task',
            recurrence='monthly',
            due_at=timezone.make_aware(datetime(2026, 1, 31, 10, 0)),
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)

    def migrate_to_latest(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_monthly_task_uses_current_due_day_as_anchor(self):
        task = Task.objects.get(pk=self.task_id)

        self.assertEqual(task.recurrence_day, 31)
