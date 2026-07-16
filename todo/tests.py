from django.test import TestCase, Client
from django.utils import timezone
from datetime import datetime
from todo.models import Task

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
        data = {'title': 'Test Task', 'tag': 'study', 'due_at': '2024-06-30 23:59:59'}
        response = client.post('/', data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(len(response.context['tasks']), 1)
        self.assertEqual(response.context['tasks'][0].tag, 'study')

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

    def test_detail_get_success(self):
        task = Task(title='task1', tag='study', due_at=timezone.make_aware(datetime(2024, 7, 1)))
        task.save()
        client = Client()
        response = client.get('/{}/'.format(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/detail.html')
        self.assertEqual(response.context['task'], task)
        self.assertContains(response, 'Tag: study')

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
        data = {'title': 'Updated Task', 'tag': 'work', 'due_at': '2024-08-01 23:59:59'}
        response = client.post('/{}/update'.format(task.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Task')
        self.assertEqual(task.tag, 'work')
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
