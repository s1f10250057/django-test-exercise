from django.core import mail
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import datetime
from todo.models import Task, SubTask

# Create your tests here.


class SampleTestCase(TestCase):
    def test_sample(self):
        self.assertEqual(1 + 2, 3)


class TaskModelTestCase(TestCase):
    def test_create_task1(self):
        due = timezone.make_aware(datetime(2024, 6, 30, 23, 59, 59))
        task = Task(title='task1', due_at=due)
        task.save()
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.title, 'task1')
        self.assertEqual(task.tag, '')
        self.assertEqual(task.recurrence, Task.RECURRENCE_NONE)
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, due)

    def test_create_task2(self):
        task = Task(title='task2')
        task.save()
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.title, 'task2')
        self.assertEqual(task.tag, '')
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, None)

    def test_create_task_with_tag(self):
        task = Task(title='task1', tag='school')
        task.save()
        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.tag, 'school')

    def test_delete_task_deletes_subtasks(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        task.delete()
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 0)

    def test_next_due_at_daily(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task(title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 7, 2, 10, 0, 0)))

    def test_next_due_at_weekly(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task(title='task1', recurrence=Task.RECURRENCE_WEEKLY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 7, 8, 10, 0, 0)))

    def test_next_due_at_monthly(self):
        due = timezone.make_aware(datetime(2024, 1, 31, 10, 0, 0))
        task = Task(title='task1', recurrence=Task.RECURRENCE_MONTHLY, due_at=due)
        self.assertEqual(task.next_due_at(), timezone.make_aware(datetime(2024, 2, 29, 10, 0, 0)))

    def test_create_next_occurrence(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task.objects.create(
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
        task = Task(title='task1', due_at=due)
        task.save()
        self.assertFalse(task.is_overdue(current))

    def test_is_overdue_past(self):
        due = timezone.make_aware(datetime(2024, 6, 30, 23, 59, 59))
        current = timezone.make_aware(datetime(2024, 7, 1, 0, 0, 0))
        task = Task(title='task1', due_at=due)
        task.save()
        self.assertTrue(task.is_overdue(current))

    def test_is_overdue_none(self):
        current = timezone.make_aware(datetime(2024, 7, 1, 0, 0, 0))
        task = Task(title='task1')
        task.save()
        self.assertFalse(task.is_overdue(current))


class TodoViewTestCase(TestCase):
    def test_index_get(self):
        client = Client()
        respose = client.get('/')
        self.assertEqual(respose.status_code, 200)
        self.assertEqual(respose.templates[0].name, 'todo/index.html')
        self.assertEqual(len(respose.context['tasks']), 0)

    def test_index_post(self):
        client = Client()
        data = {
            'title': 'Test Task',
            'tag': 'study',
            'recurrence': Task.RECURRENCE_DAILY,
            'due_at': '2024-06-30 23:59:59',
        }
        response = client.post('/', data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(len(response.context['tasks']), 1)
        self.assertEqual(response.context['tasks'][0].tag, 'study')
        self.assertEqual(response.context['tasks'][0].recurrence, Task.RECURRENCE_DAILY)

    def test_index_post_without_tag(self):
        client = Client()
        data = {'title': 'Test Task', 'due_at': '2024-06-30 23:59:59'}
        response = client.post('/', data)
        self.assertEqual(response.status_code, 200)
        task = response.context['tasks'][0]
        self.assertEqual(task.tag, '')

    def test_index_get_order_post(self):
        task1 = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task1.save()
        task2 = Task(title='task2', due_at=timezone.make_aware(datetime(2024, 8, 1)))
        task2.save()
        client = Client()
        response = client.get('/?order=post')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task2)
        self.assertEqual(response.context['tasks'][1], task1)

    def test_index_get_order_due(self):
        task1 = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task1.save()
        task2 = Task(title='task2', due_at=timezone.make_aware(datetime(2024, 8, 1)))
        task2.save()
        client = Client()
        response = client.get('/?order=due')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task1)
        self.assertEqual(response.context['tasks'][1], task2)

    def test_index_get_order_tag(self):
        task1 = Task(title='task1', tag='work')
        task1.save()
        task2 = Task(title='task2', tag='study')
        task2.save()
        client = Client()
        response = client.get('/?order=tag')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(response.context['tasks'][0], task2)
        self.assertEqual(response.context['tasks'][1], task1)

    def test_detail_get_success(self):
        task = Task(title='task1', tag='study', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        subtask = SubTask.objects.create(task=task, title='subtask1')
        client = Client()
        response = client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/detail.html')
        self.assertEqual(response.context['task'], task)
        self.assertEqual(response.context['subtasks'][0], subtask)
        self.assertContains(response, 'Tag: study')
        self.assertContains(response, 'subtask1: Not Completed')

    def test_detail_get_fail(self):
        client = Client()
        response = client.get('/1/')
        self.assertEqual(response.status_code, 404)

    def test_delete_post_success(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.post('/{}/delete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        self.assertEqual(Task.objects.filter(pk=task.pk).count(), 0)

    def test_delete_get_not_allowed(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.get('/{}/delete/'.format(task.pk))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Task.objects.filter(pk=task.pk).count(), 1)


    def test_delete_post_fail(self):
        client = Client()
        response = client.post('/1/delete/')
        
    def test_update_get_success(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.get('/{}/update'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/edit.html')
        self.assertEqual(response.context['task'], task)

    def test_update_post_success(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        data = {
            'title': 'Updated Task',
            'tag': 'work',
            'recurrence': Task.RECURRENCE_WEEKLY,
            'due_at': '2024-08-01 23:59:59',
        }
        response = client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Task')
        self.assertEqual(task.tag, 'work')
        self.assertEqual(task.recurrence, Task.RECURRENCE_WEEKLY)
        self.assertEqual(task.due_at, timezone.make_aware(datetime(2024, 8, 1, 23, 59, 59)))

    def test_update_post_without_tag(self):
        task = Task(title='task1', tag='study', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        data = {'title': 'Updated Task', 'due_at': '2024-08-01 23:59:59'}
        response = client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.tag, '')

    def test_update_get_fail(self):
        client = Client()
        response = client.get('/1/update')
        self.assertEqual(response.status_code, 404)

    def test_update_post_fail(self):
        client = Client()
        response = client.post('/1/update', {'title': 'Updated Task', 'due_at': '2024-08-01 23:59:59'})
        self.assertEqual(response.status_code, 404)

    def test_complete_post_success(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        task.refresh_from_db()
        self.assertTrue(task.completed)

    def test_complete_post_creates_next_recurring_task(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task.objects.create(title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        client = Client()
        response = client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 302)
        next_task = Task.objects.exclude(pk=task.pk).get()
        self.assertEqual(next_task.title, 'task1')
        self.assertEqual(next_task.due_at, timezone.make_aware(datetime(2024, 7, 2, 10, 0, 0)))

    def test_complete_post_creates_one_next_task_only_once(self):
        due = timezone.make_aware(datetime(2024, 7, 1, 10, 0, 0))
        task = Task.objects.create(title='task1', recurrence=Task.RECURRENCE_DAILY, due_at=due)
        client = Client()
        client.post('/{}/complete/'.format(task.pk))
        client.post('/{}/complete/'.format(task.pk))
        self.assertEqual(Task.objects.exclude(pk=task.pk).count(), 1)

    def test_complete_get_not_allowed(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.get('/{}/complete/'.format(task.pk))
        self.assertEqual(response.status_code, 405)
        task.refresh_from_db()
        self.assertFalse(task.completed)

    def test_complete_post_updates_index_status(self):
        task = Task(title='task1', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        client.post('/{}/complete/'.format(task.pk))
        response = client.get('/')
        self.assertContains(response, 'Status: Completed')
        self.assertNotContains(response, '<button type="submit">Complete</button>', html=True)

    def test_detail_hides_complete_button_when_completed(self):
        task = Task(title='task1', completed=True, due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Status: Completed')
        self.assertNotContains(response, '<button type="submit">Complete</button>', html=True)

    def test_complete_post_fail(self):
        client = Client()
        response = client.post('/1/complete/')
        self.assertEqual(response.status_code, 404)

    def test_add_subtask_post_success(self):
        task = Task.objects.create(title='task1')
        client = Client()
        response = client.post('/{}/subtasks/add/'.format(task.pk), {'title': 'subtask1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        subtask = SubTask.objects.get(task=task)
        self.assertEqual(subtask.title, 'subtask1')
        self.assertFalse(subtask.completed)

    def test_add_subtask_post_empty_title(self):
        task = Task.objects.create(title='task1')
        client = Client()
        response = client.post('/{}/subtasks/add/'.format(task.pk), {'title': '   '})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SubTask.objects.filter(task=task).count(), 0)

    def test_add_subtask_get_not_allowed(self):
        task = Task.objects.create(title='task1')
        client = Client()
        response = client.get('/{}/subtasks/add/'.format(task.pk))
        self.assertEqual(response.status_code, 405)

    def test_toggle_subtask_post_success(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        client = Client()
        response = client.post('/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        subtask.refresh_from_db()
        self.assertTrue(subtask.completed)

    def test_toggle_subtask_get_not_allowed(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        client = Client()
        response = client.get('/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 405)
        subtask.refresh_from_db()
        self.assertFalse(subtask.completed)

    def test_delete_subtask_post_success(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        client = Client()
        response = client.post('/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 0)

    def test_delete_subtask_get_not_allowed(self):
        task = Task.objects.create(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        client = Client()
        response = client.get('/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(SubTask.objects.filter(pk=subtask.pk).count(), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotifyDueTasksCommandTestCase(TestCase):
    def test_notify_due_tasks_sends_due_soon_task(self):
        due = timezone.now() + timezone.timedelta(hours=12)
        task = Task.objects.create(title='task1', due_at=due)
        call_command('notify_due_tasks', recipient='student@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('task1', mail.outbox[0].body)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)

    def test_notify_due_tasks_skips_completed_and_far_tasks(self):
        Task.objects.create(title='completed', completed=True, due_at=timezone.now() + timezone.timedelta(hours=12))
        Task.objects.create(title='far', due_at=timezone.now() + timezone.timedelta(days=3))
        call_command('notify_due_tasks', recipient='student@example.com')
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_due_tasks_does_not_send_duplicate_notifications(self):
        task = Task.objects.create(title='task1', due_at=timezone.now() + timezone.timedelta(hours=12))
        call_command('notify_due_tasks', recipient='student@example.com')
        call_command('notify_due_tasks', recipient='student@example.com')
        self.assertEqual(len(mail.outbox), 1)
        task.refresh_from_db()
        self.assertIsNotNone(task.notified_at)
