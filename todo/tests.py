from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from todo.models import Task, SubTask

# Create your tests here.


class SampleTestCase(TestCase):
    def test_sample(self):
        self.assertEqual(1 + 2, 3)


class TaskModelTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password')

    def create_task(self, **kwargs):
        kwargs.setdefault('owner', self.owner)
        return Task.objects.create(**kwargs)

    def test_create_task1(self):
        due = timezone.make_aware(datetime(2024, 6, 30, 23, 59, 59))
        task = self.create_task(title='task1', due_at=due)
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.title, 'task1')
        self.assertEqual(task.tag, '')
        self.assertEqual(task.recurrence, Task.RECURRENCE_NONE)
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, due)

    def test_create_task2(self):
        task = self.create_task(title='task2')
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.title, 'task2')
        self.assertEqual(task.tag, '')
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, None)

    def test_create_task_with_tag(self):
        task = self.create_task(title='task1', tag='school')
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.tag, 'school')

    def test_delete_task_deletes_subtasks(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        task.delete()
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 0)

    def test_next_due_at_daily(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task(owner=self.owner, title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 7, 2, 10, 0, 0)))

    def test_next_due_at_weekly(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task(owner=self.owner, title='task1', recurrence=Task.RECURRENCE_WEEKLY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 7, 8, 10, 0, 0)))

    def test_next_due_at_monthly(self):
        due = timezone.make_aware(datetime(2024, 1, 31, 10, 0, 0))
        task = Task(owner=self.owner, title='task1', recurrence=Task.RECURRENCE_MONTHLY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 2, 29, 10, 0, 0)))

    def test_create_next_occurrence(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = self.create_task(
            title='task1',
            tag='study',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )
        next_task = task.create_next_occurrence()
        self.assertEqual(next_task.title, 'task1')
        self.assertEqual(next_task.tag, 'study')
        self.assertEqual(next_task.recurrence, Task.RECURRENCE_DAILY)
        self.assertEqual(next_task.due_at, timezone.make_aware(datetime(2024, 7, 2, 10, 0, 0)))
        self.assertFalse(next_task.completed)

    def test_is_overdue_future(self):
        due = timezone.make_aware(datetime(2024, 6, 30, 23, 59, 59))
        current = timezone.make_aware(datetime(2024, 6, 30, 0, 0, 0))
        task = self.create_task(title='task1', due_at=due)
        self.assertFalse(task.is_overdue(current))

    def test_is_overdue_past(self):
        due = timezone.make_aware(datetime(2024, 6, 30, 23, 59, 59))
        current = timezone.make_aware(datetime(2024, 7, 1, 0, 0, 0))
        task = self.create_task(title='task1', due_at=due)
        self.assertTrue(task.is_overdue(current))

    def test_is_overdue_none(self):
        current = timezone.make_aware(datetime(2024, 7, 1, 0, 0, 0))
        task = self.create_task(title='task1')
        self.assertFalse(task.is_overdue(current))


class TodoViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='password')
        self.other_user = User.objects.create_user(username='bob', password='password')
        self.client = Client()
        self.client.force_login(self.user)

    def create_task(self, **kwargs):
        kwargs.setdefault('owner', self.user)
        task = Task(**kwargs)
        task.save()
        return task

    def test_index_requires_login(self):
        self.client.logout()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/')

    def test_login_get(self):
        self.client.logout()
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'registration/login.html')

    def test_login_post_success(self):
        self.client.logout()
        data = {'username': 'alice', 'password': 'password'}
        response = self.client.post('/login/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_logout_post_success(self):
        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/')

    def test_index_get(self):
        respose = self.client.get('/')
        self.assertEqual(respose.status_code, 200)
        self.assertEqual(respose.templates[0].name, 'todo/index.html')
        self.assertEqual(len(respose.context['tasks']), 0)

    def test_index_post(self):
        data = {
            'title': 'Test Task',
            'tag': 'study',
            'recurrence': Task.RECURRENCE_DAILY,
            'due_at': '2024-06-30 23:59:59',
        }
        response = self.client.post('/', data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(len(response.context['tasks']), 1)
        self.assertEqual(response.context['tasks'][0].tag, 'study')
        self.assertEqual(response.context['tasks'][0].owner, self.user)
        self.assertEqual(response.context['tasks'][0].recurrence, Task.RECURRENCE_DAILY)

    def test_index_post_without_tag(self):
        data = {'title': 'Test Task', 'due_at': '2024-06-30 23:59:59'}
        response = self.client.post('/', data)
        self.assertEqual(response.status_code, 200)
        task = response.context['tasks'][0]
        self.assertEqual(task.tag, '')
        self.assertEqual(task.owner, self.user)

    def test_index_get_only_own_tasks(self):
        own_task = self.create_task(title='own task')
        Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.get('/')
        self.assertEqual(list(response.context['tasks']), [own_task])
        self.assertContains(response, 'own task')
        self.assertNotContains(response, 'other task')

    def test_index_get_order_post(self):
        task1 = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task2 = self.create_task(title='task2', due_at=timezone.make_aware(datetime(2024, 8, 1)))
        response = self.client.get('/?order=post')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task2)
        self.assertEqual(response.context['tasks'][1], task1)

    def test_index_get_order_due(self):
        task1 = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task2 = self.create_task(title='task2', due_at=timezone.make_aware(datetime(2024, 8, 1)))
        response = self.client.get('/?order=due')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task1)
        self.assertEqual(response.context['tasks'][1], task2)

    def test_index_get_order_tag(self):
        task1 = self.create_task(title='task1', tag='work')
        task2 = self.create_task(title='task2', tag='study')
        response = self.client.get('/?order=tag')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task2)
        self.assertEqual(response.context['tasks'][1], task1)

    def test_detail_get_success(self):
        task = self.create_task(title='task1', tag='study',
                                due_at=timezone.make_aware(datetime(2024, 7, 1)))
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/detail.html')
        self.assertEqual(response.context['task'], task)
        self.assertEqual(response.context['subtasks'][0], subtask)
        self.assertContains(response, 'Tag: study')
        self.assertContains(response, 'subtask1: Not Completed')

    def test_detail_requires_login(self):
        task = self.create_task(title='task1')
        self.client.logout()
        response = self.client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/{}/'.format(task.pk))

    def test_detail_get_fail(self):
        response = self.client.get('/1/')
        self.assertEqual(response.status_code, 404)

    def test_detail_get_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 404)

    def test_delete_post_success(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.post('/{}/delete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        self.assertEqual(Task.objects.filter(pk=task.pk).count(), 0)

    def test_delete_get_not_allowed(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.get('/{}/delete/'.format(task.pk))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Task.objects.filter(pk=task.pk).count(), 1)

    def test_delete_post_fail(self):
        response = self.client.post('/1/delete/')
        self.assertEqual(response.status_code, 404)

    def test_delete_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.post('/{}/delete/'.format(task.pk))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Task.objects.filter(pk=task.pk).count(), 1)

    def test_update_get_success(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.get('/{}/update'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/edit.html')
        self.assertEqual(response.context['task'], task)

    def test_update_post_success(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        data = {
            'title': 'Updated Task',
            'tag': 'work',
            'recurrence': Task.RECURRENCE_WEEKLY,
            'due_at': '2024-08-01 23:59:59',
        }
        response = self.client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Task')
        self.assertEqual(task.tag, 'work')
        self.assertEqual(task.recurrence, Task.RECURRENCE_WEEKLY)
        self.assertEqual(task.due_at, timezone.make_aware(datetime(2024, 8, 1, 23, 59, 59)))

    def test_update_post_without_tag(self):
        task = self.create_task(title='task1', tag='study',
                                due_at=timezone.make_aware(datetime(2024, 7, 1)))
        data = {'title': 'Updated Task', 'due_at': '2024-08-01 23:59:59'}
        response = self.client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.tag, '')

    def test_update_get_fail(self):
        response = self.client.get('/1/update')
        self.assertEqual(response.status_code, 404)

    def test_update_post_fail(self):
        response = self.client.post('/1/update', {'title': 'Updated Task', 'due_at': '2024-08-01 23:59:59'})
        self.assertEqual(response.status_code, 404)

    def test_update_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        data = {'title': 'Updated Task', 'due_at': '2024-08-01 23:59:59'}
        response = self.client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.title, 'other task')

    def test_complete_post_success(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        task.refresh_from_db()
        self.assertTrue(task.completed)

    def test_complete_post_creates_next_recurring_task(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = self.create_task(title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        response = self.client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        next_task = Task.objects.exclude(pk=task.pk).get()
        self.assertEqual(next_task.title, 'task1')
        self.assertEqual(next_task.owner, self.user)
        self.assertEqual(next_task.due_at, timezone.make_aware(datetime(2024, 7, 2, 10, 0, 0)))

    def test_complete_post_creates_one_next_task_only_once(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = self.create_task(title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        self.client.post('/{}/complete/'.format(task.pk))
        self.client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(Task.objects.exclude(pk=task.pk).count(), 1)

    def test_complete_get_not_allowed(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.get('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 405)
        task.refresh_from_db()
        self.assertFalse(task.completed)

    def test_complete_post_updates_index_status(self):
        task = self.create_task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        self.client.post('/{}/complete/'.format(task.pk))
        response = self.client.get('/')
        self.assertContains(response, 'Status: Completed')
        self.assertNotContains(response, '<button type="submit">Complete</button>', html=True)

    def test_detail_hides_complete_button_when_completed(self):
        task = self.create_task(title='task1', completed=True,
                                due_at=timezone.make_aware(datetime(2024, 7, 1)))
        response = self.client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Status: Completed')
        self.assertNotContains(response, '<button type="submit">Complete</button>', html=True)

    def test_complete_post_fail(self):
        response = self.client.post('/1/complete/')
        self.assertEqual(response.status_code, 404)

    def test_complete_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertFalse(task.completed)

    def test_add_subtask_post_success(self):
        task = self.create_task(title='task1')
        response = self.client.post('/{}/subtasks/add/'.format(task.pk), {'title': 'subtask1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        subtask = SubTask.objects.get(task=task)
        self.assertEqual(subtask.title, 'subtask1')
        self.assertFalse(subtask.completed)

    def test_add_subtask_post_empty_title(self):
        task = self.create_task(title='task1')
        response = self.client.post('/{}/subtasks/add/'.format(task.pk), {'title': '   '})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SubTask.objects.filter(task=task).count(), 0)

    def test_add_subtask_get_not_allowed(self):
        task = self.create_task(title='task1')
        response = self.client.get('/{}/subtasks/add/'.format(task.pk))
        self.assertEqual(response.status_code, 405)

    def test_add_subtask_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.post('/{}/subtasks/add/'.format(task.pk), {'title': 'subtask1'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(SubTask.objects.filter(task=task).count(), 0)

    def test_toggle_subtask_post_success(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.post('/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        subtask.refresh_from_db()
        self.assertTrue(subtask.completed)

    def test_toggle_subtask_get_not_allowed(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.get('/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 405)
        subtask.refresh_from_db()
        self.assertFalse(subtask.completed)

    def test_toggle_subtask_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.post('/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 404)
        subtask.refresh_from_db()
        self.assertFalse(subtask.completed)

    def test_delete_subtask_post_success(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.post('/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 0)

    def test_delete_subtask_get_not_allowed(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.get('/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 1)

    def test_delete_subtask_post_other_user_task_fail(self):
        task = Task.objects.create(title='other task', owner=self.other_user)
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.post('/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 1)

    def test_create_task_with_description(self):
        task = Task(title='Task with Desc', description='This is a memo.')
        task.save()
        saved_task = Task.objects.get(pk=task.pk)
        self.assertEqual(saved_task.description, 'This is a memo.')

    def test_create_task_without_description(self):
        task = Task(title='No Desc Task')
        task.save()
        saved_task = Task.objects.get(pk=task.pk)
        self.assertIn(saved_task.description, [None, ''])



@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotifyDueTasksCommandTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='password',
        )

    def create_task(self, **kwargs):
        kwargs.setdefault('owner', self.owner)
        return Task.objects.create(**kwargs)

    def test_notify_due_tasks_sends_due_soon_task(self):
        due = timezone.now() + timezone.timedelta(hours=12)
        task = self.create_task(title='task1', due_at=due)
        call_command('notify_due_tasks')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertIn('task1', mail.outbox[0].body)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)

    def test_notify_due_tasks_skips_completed_and_far_tasks(self):
        self.create_task(title='completed', completed=True,
                         due_at=timezone.now() + timezone.timedelta(hours=12))
        self.create_task(title='far', due_at=timezone.now() + timezone.timedelta(days=3))
        call_command('notify_due_tasks')
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_due_tasks_does_not_send_duplicate_notifications(self):
        task = self.create_task(title='task1', due_at=timezone.now() + timezone.timedelta(hours=12))
        call_command('notify_due_tasks')
        call_command('notify_due_tasks')
        self.assertEqual(len(mail.outbox), 1)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)

    def test_notify_due_tasks_only_sends_selected_owner_tasks(self):
        due = timezone.now() + timezone.timedelta(hours=12)
        alice = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='password',
        )
        bob = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='password',
        )
        alice_task = Task.objects.create(title='alice task', owner=alice, due_at=due)
        bob_task = Task.objects.create(title='bob task', owner=bob, due_at=due)

        call_command('notify_due_tasks', owner='alice')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])
        self.assertIn('alice task', mail.outbox[0].body)
        self.assertNotIn('bob task', mail.outbox[0].body)
        alice_task.refresh_from_db()
        bob_task.refresh_from_db()
        self.assertIsNotNone(alice_task.notified_at)
        self.assertIsNone(bob_task.notified_at)

    def test_notify_due_tasks_keeps_owner_notifications_separate(self):
        due = timezone.now() + timezone.timedelta(hours=12)
        bob = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='password',
        )
        self.create_task(title='owner private', due_at=due)
        Task.objects.create(title='bob private', owner=bob, due_at=due)

        call_command('notify_due_tasks')

        self.assertEqual(len(mail.outbox), 2)
        messages = {message.to[0]: message.body for message in mail.outbox}
        self.assertIn('owner private', messages['owner@example.com'])
        self.assertNotIn('bob private', messages['owner@example.com'])
        self.assertIn('bob private', messages['bob@example.com'])
        self.assertNotIn('owner private', messages['bob@example.com'])

    def test_notify_due_tasks_skips_owner_without_email(self):
        due = timezone.now() + timezone.timedelta(hours=12)
        owner_without_email = User.objects.create_user(username='no-email', password='password')
        task = Task.objects.create(title='private task', owner=owner_without_email, due_at=due)

        call_command('notify_due_tasks')

        self.assertEqual(len(mail.outbox), 0)
        task.refresh_from_db()
        self.assertIsNone(task.notified_at)


class TaskAdminTestCase(TestCase):
    def test_superuser_can_assign_owner_to_legacy_task(self):
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password',
        )
        legacy_owner = User.objects.create_user(username='legacy-owner', is_active=False)
        owner = User.objects.create_user(username='owner', password='password')
        legacy_task = Task.objects.create(title='legacy task', owner=legacy_owner)
        self.client.force_login(superuser)

        response = self.client.post(
            reverse('admin:todo_task_change', args=[legacy_task.pk]),
            {
                'owner': owner.pk,
                'title': legacy_task.title,
                'tag': legacy_task.tag,
                'recurrence': legacy_task.recurrence,
                'posted_at_0': legacy_task.posted_at.date().isoformat(),
                'posted_at_1': legacy_task.posted_at.time().strftime('%H:%M:%S'),
                'due_at_0': '',
                'due_at_1': '',
                'notified_at_0': '',
                'notified_at_1': '',
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 302)
        legacy_task.refresh_from_db()
        self.assertEqual(legacy_task.owner, owner)
