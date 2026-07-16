from datetime import datetime

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from todo.models import SubTask, Task


class TaskModelTestCase(TestCase):
    def test_create_task_with_management_fields(self):
        due = timezone.make_aware(datetime(2026, 7, 31, 23, 59))
        task = Task.objects.create(
            title='レポート提出',
            tag='Django',
            due_at=due,
            status=Task.Status.DOING,
            priority=Task.Priority.HIGH,
            category=Task.Category.UNIVERSITY,
            recurrence=Task.RECURRENCE_WEEKLY,
        )

        task.refresh_from_db()
        self.assertEqual(task.tag, 'Django')
        self.assertEqual(task.status, Task.Status.DOING)
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.category, Task.Category.UNIVERSITY)
        self.assertEqual(task.recurrence, Task.RECURRENCE_WEEKLY)
        self.assertEqual(task.due_at, due)

    def test_create_task_uses_defaults(self):
        task = Task.objects.create(title='デフォルト値の確認')

        self.assertEqual(task.tag, '')
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)
        self.assertEqual(task.category, Task.Category.OTHER)
        self.assertEqual(task.recurrence, Task.RECURRENCE_NONE)
        self.assertIsNone(task.due_at)

    def test_delete_task_deletes_subtasks(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')

        task.delete()

        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_next_due_at_daily(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = Task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )

        self.assertEqual(
            task.next_due_at(),
            timezone.make_aware(datetime(2026, 7, 2, 10, 0)),
        )

    def test_next_due_at_weekly(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = Task(
            title='task1',
            recurrence=Task.RECURRENCE_WEEKLY,
            due_at=due,
        )

        self.assertEqual(
            task.next_due_at(),
            timezone.make_aware(datetime(2026, 7, 8, 10, 0)),
        )

    def test_next_due_at_monthly_adjusts_last_day(self):
        due = timezone.make_aware(datetime(2024, 1, 31, 10, 0))
        task = Task(
            title='task1',
            recurrence=Task.RECURRENCE_MONTHLY,
            due_at=due,
        )

        self.assertEqual(
            task.next_due_at(),
            timezone.make_aware(datetime(2024, 2, 29, 10, 0)),
        )

    def test_create_next_occurrence_inherits_management_fields(self):
        owner = User.objects.create_user(username='alice')
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = Task.objects.create(
            owner=owner,
            title='task1',
            tag='study',
            priority=Task.Priority.HIGH,
            category=Task.Category.UNIVERSITY,
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )

        next_task = task.create_next_occurrence()

        self.assertEqual(next_task.owner, owner)
        self.assertEqual(next_task.title, 'task1')
        self.assertEqual(next_task.tag, 'study')
        self.assertEqual(next_task.priority, Task.Priority.HIGH)
        self.assertEqual(next_task.category, Task.Category.UNIVERSITY)
        self.assertEqual(next_task.status, Task.Status.TODO)
        self.assertEqual(next_task.recurrence, Task.RECURRENCE_DAILY)
        self.assertEqual(
            next_task.due_at,
            timezone.make_aware(datetime(2026, 7, 2, 10, 0)),
        )

    def test_create_next_occurrence_does_not_duplicate(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = Task.objects.create(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )

        first = task.create_next_occurrence()
        second = task.create_next_occurrence()

        self.assertEqual(first, second)
        self.assertEqual(Task.objects.exclude(pk=task.pk).count(), 1)

    def test_is_overdue_future(self):
        due = timezone.make_aware(datetime(2026, 7, 31, 23, 59))
        current = timezone.make_aware(datetime(2026, 7, 30, 0, 0))
        task = Task.objects.create(title='task1', due_at=due)

        self.assertFalse(task.is_overdue(current))

    def test_is_overdue_past(self):
        due = timezone.make_aware(datetime(2026, 7, 30, 23, 59))
        current = timezone.make_aware(datetime(2026, 7, 31, 0, 0))
        task = Task.objects.create(title='task1', due_at=due)

        self.assertTrue(task.is_overdue(current))

    def test_is_overdue_without_due_date(self):
        current = timezone.make_aware(datetime(2026, 7, 31, 0, 0))
        task = Task.objects.create(title='task1')

        self.assertFalse(task.is_overdue(current))


class TodoViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice',
            password='password',
        )
        self.other_user = User.objects.create_user(
            username='bob',
            password='password',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def create_task(self, **kwargs):
        kwargs.setdefault('owner', self.user)
        return Task.objects.create(**kwargs)

    def task_data(self, **overrides):
        data = {
            'title': 'Test Task',
            'tag': 'study',
            'due_at': '2026-07-31T23:59',
            'status': Task.Status.TODO,
            'priority': Task.Priority.MEDIUM,
            'category': Task.Category.OTHER,
            'recurrence': Task.RECURRENCE_NONE,
        }
        data.update(overrides)
        return data

    def test_index_requires_login(self):
        self.client.logout()

        response = self.client.get('/')

        self.assertRedirects(response, '/login/?next=/', fetch_redirect_response=False)

    def test_login_get(self):
        self.client.logout()

        response = self.client.get('/login/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_login_post_success(self):
        self.client.logout()

        response = self.client.post(
            '/login/',
            {'username': 'alice', 'password': 'password'},
        )

        self.assertRedirects(response, '/')

    def test_logout_post_success(self):
        response = self.client.post('/logout/')

        self.assertRedirects(response, '/login/')

    def test_index_get_has_three_board_columns(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'todo/index.html')
        self.assertEqual(len(response.context['tasks']), 0)
        self.assertEqual(len(response.context['columns']), 3)
        self.assertContains(response, '未着手')
        self.assertContains(response, '進行中')
        self.assertContains(response, '完了')

    def test_index_post_creates_owned_task_and_redirects(self):
        response = self.client.post(
            '/',
            self.task_data(
                priority=Task.Priority.HIGH,
                category=Task.Category.UNIVERSITY,
                recurrence=Task.RECURRENCE_WEEKLY,
            ),
        )

        self.assertRedirects(response, '/')
        task = Task.objects.get()
        self.assertEqual(task.owner, self.user)
        self.assertEqual(task.tag, 'study')
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.category, Task.Category.UNIVERSITY)
        self.assertEqual(task.recurrence, Task.RECURRENCE_WEEKLY)

    def test_index_post_accepts_empty_due_date_and_tag(self):
        response = self.client.post(
            '/',
            self.task_data(due_at='', tag=''),
        )

        self.assertRedirects(response, '/')
        task = Task.objects.get()
        self.assertIsNone(task.due_at)
        self.assertEqual(task.tag, '')

    def test_index_post_rejects_empty_title(self):
        response = self.client.post('/', self.task_data(title=''))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)
        self.assertContains(response, 'このフィールドは必須です')

    def test_index_only_shows_own_tasks(self):
        own_task = self.create_task(title='own task')
        Task.objects.create(title='other task', owner=self.other_user)
        Task.objects.create(title='legacy task')

        response = self.client.get('/')

        self.assertEqual(list(response.context['tasks']), [own_task])
        self.assertContains(response, 'own task')
        self.assertNotContains(response, 'other task')
        self.assertNotContains(response, 'legacy task')

    def test_index_orders_by_posted_date(self):
        older = self.create_task(title='older')
        newer = self.create_task(title='newer')

        response = self.client.get('/?order=post')

        self.assertEqual(list(response.context['tasks']), [newer, older])

    def test_index_orders_by_due_date_with_empty_dates_last(self):
        no_due = self.create_task(title='no due')
        later = self.create_task(
            title='later',
            due_at=timezone.make_aware(datetime(2026, 8, 1)),
        )
        earlier = self.create_task(
            title='earlier',
            due_at=timezone.make_aware(datetime(2026, 7, 20)),
        )

        response = self.client.get('/?order=due')

        self.assertEqual(
            list(response.context['tasks']),
            [earlier, later, no_due],
        )

    def test_index_orders_by_tag(self):
        work = self.create_task(title='work task', tag='work')
        study = self.create_task(title='study task', tag='study')

        response = self.client.get('/?order=tag')

        self.assertEqual(list(response.context['tasks']), [study, work])

    def test_index_searches_title_and_tag(self):
        title_match = self.create_task(title='Djangoレポート')
        tag_match = self.create_task(title='課題', tag='Django')
        self.create_task(title='買い物', tag='personal')

        response = self.client.get('/?q=django')

        self.assertEqual(
            set(response.context['tasks']),
            {title_match, tag_match},
        )

    def test_index_filters_status_priority_and_category(self):
        expected = self.create_task(
            title='該当タスク',
            status=Task.Status.DOING,
            priority=Task.Priority.HIGH,
            category=Task.Category.UNIVERSITY,
        )
        self.create_task(
            title='対象外タスク',
            status=Task.Status.TODO,
            priority=Task.Priority.LOW,
            category=Task.Category.PERSONAL,
        )

        response = self.client.get(
            '/?status=doing&priority=high&category=university'
        )

        self.assertEqual(list(response.context['tasks']), [expected])

    def test_detail_includes_tag_recurrence_and_subtasks(self):
        task = self.create_task(
            title='task1',
            tag='study',
            priority=Task.Priority.HIGH,
            recurrence=Task.RECURRENCE_DAILY,
        )
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.get('/{}/'.format(task.pk))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'todo/detail.html')
        self.assertEqual(response.context['task'], task)
        self.assertEqual(list(response.context['subtasks']), [subtask])
        self.assertContains(response, '優先度 高')
        self.assertContains(response, '#study')
        self.assertContains(response, '毎日')
        self.assertContains(response, 'subtask1')

    def test_detail_requires_login(self):
        task = self.create_task(title='task1')
        self.client.logout()

        response = self.client.get('/{}/'.format(task.pk))

        self.assertEqual(response.status_code, 302)

    def test_detail_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.get('/{}/'.format(task.pk))

        self.assertEqual(response.status_code, 404)

    def test_update_post_updates_all_editable_fields(self):
        task = self.create_task(title='task1')
        data = self.task_data(
            title='Updated Task',
            tag='work',
            status=Task.Status.DOING,
            priority=Task.Priority.HIGH,
            category=Task.Category.PERSONAL,
            recurrence=Task.RECURRENCE_MONTHLY,
        )

        response = self.client.post('/{}/update'.format(task.pk), data)

        self.assertRedirects(response, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.owner, self.user)
        self.assertEqual(task.title, 'Updated Task')
        self.assertEqual(task.tag, 'work')
        self.assertEqual(task.status, Task.Status.DOING)
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.category, Task.Category.PERSONAL)
        self.assertEqual(task.recurrence, Task.RECURRENCE_MONTHLY)

    def test_update_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.post(
            '/{}/update'.format(task.pk),
            self.task_data(),
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_post_success(self):
        task = self.create_task(title='task1')

        response = self.client.post('/{}/delete/'.format(task.pk))

        self.assertRedirects(response, '/')
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_delete_get_not_allowed(self):
        task = self.create_task(title='task1')

        response = self.client.get('/{}/delete/'.format(task.pk))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_delete_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.post('/{}/delete/'.format(task.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_complete_post_sets_done_status(self):
        task = self.create_task(title='task1')

        response = self.client.post('/{}/complete/'.format(task.pk))

        self.assertRedirects(response, '/')
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_complete_creates_one_next_recurring_task(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = self.create_task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )

        self.client.post('/{}/complete/'.format(task.pk))
        self.client.post('/{}/complete/'.format(task.pk))

        next_task = Task.objects.exclude(pk=task.pk).get()
        self.assertEqual(next_task.owner, self.user)
        self.assertEqual(
            next_task.due_at,
            timezone.make_aware(datetime(2026, 7, 2, 10, 0)),
        )

    def test_complete_get_not_allowed(self):
        task = self.create_task(title='task1')

        response = self.client.get('/{}/complete/'.format(task.pk))

        self.assertEqual(response.status_code, 405)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)

    def test_complete_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.post('/{}/complete/'.format(task.pk))

        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)

    def test_change_status_post_success(self):
        task = self.create_task(title='task1')

        response = self.client.post(
            '/{}/status/'.format(task.pk),
            {'status': Task.Status.DOING},
        )

        self.assertRedirects(response, '/')
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DOING)

    def test_change_status_to_done_creates_next_occurrence(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = self.create_task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )

        response = self.client.post(
            '/{}/status/'.format(task.pk),
            {'status': Task.Status.DONE},
        )

        self.assertRedirects(response, '/')
        self.assertEqual(Task.objects.exclude(pk=task.pk).count(), 1)

    def test_change_status_rejects_invalid_status(self):
        task = self.create_task(title='task1')

        response = self.client.post(
            '/{}/status/'.format(task.pk),
            {'status': 'invalid'},
        )

        self.assertEqual(response.status_code, 400)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)

    def test_change_status_get_not_allowed(self):
        task = self.create_task(title='task1')

        response = self.client.get('/{}/status/'.format(task.pk))

        self.assertEqual(response.status_code, 405)

    def test_change_status_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.post(
            '/{}/status/'.format(task.pk),
            {'status': Task.Status.DOING},
        )

        self.assertEqual(response.status_code, 404)

    def test_add_subtask_post_success(self):
        task = self.create_task(title='task1')

        response = self.client.post(
            '/{}/subtasks/add/'.format(task.pk),
            {'title': 'subtask1'},
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        subtask = SubTask.objects.get(task=task)
        self.assertEqual(subtask.title, 'subtask1')

    def test_add_subtask_ignores_empty_title(self):
        task = self.create_task(title='task1')

        response = self.client.post(
            '/{}/subtasks/add/'.format(task.pk),
            {'title': '   '},
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        self.assertFalse(SubTask.objects.filter(task=task).exists())

    def test_add_subtask_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)

        response = self.client.post(
            '/{}/subtasks/add/'.format(task.pk),
            {'title': 'subtask1'},
        )

        self.assertEqual(response.status_code, 404)

    def test_toggle_subtask_post_success(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.post(
            '/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk)
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        subtask.refresh_from_db()
        self.assertTrue(subtask.completed)

    def test_toggle_subtask_get_not_allowed(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.get(
            '/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk)
        )

        self.assertEqual(response.status_code, 405)

    def test_toggle_subtask_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.post(
            '/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk)
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_subtask_post_success(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.post(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk)
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_delete_subtask_get_not_allowed(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.get(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk)
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_delete_subtask_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)
        subtask = SubTask.objects.create(task=task, title='subtask1')

        response = self.client.post(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk)
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(SubTask.objects.filter(pk=subtask.pk).exists())


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class NotifyDueTasksCommandTestCase(TestCase):
    def test_notify_due_tasks_sends_due_soon_task(self):
        task = Task.objects.create(
            title='task1',
            due_at=timezone.now() + timezone.timedelta(hours=12),
        )

        call_command(
            'notify_due_tasks',
            recipient='student@example.com',
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('task1', mail.outbox[0].body)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)

    def test_notify_due_tasks_skips_done_and_far_tasks(self):
        Task.objects.create(
            title='done',
            status=Task.Status.DONE,
            due_at=timezone.now() + timezone.timedelta(hours=12),
        )
        Task.objects.create(
            title='far',
            due_at=timezone.now() + timezone.timedelta(days=3),
        )

        call_command(
            'notify_due_tasks',
            recipient='student@example.com',
        )

        self.assertEqual(len(mail.outbox), 0)

    def test_notify_due_tasks_does_not_send_duplicates(self):
        task = Task.objects.create(
            title='task1',
            due_at=timezone.now() + timezone.timedelta(hours=12),
        )

        call_command(
            'notify_due_tasks',
            recipient='student@example.com',
        )
        call_command(
            'notify_due_tasks',
            recipient='student@example.com',
        )

        self.assertEqual(len(mail.outbox), 1)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)
