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
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, due)

    def test_create_task2(self):
        task = Task(title='task2')
        task.save()

        task = Task.objects.get(pk=task.pk)
        self.assertEqual(task.title, 'task2')
        self.assertFalse(task.completed)
        self.assertEqual(task.due_at, None)

    def test_is_overdue_future(self):
            due = timezone.make_aware(datetime(2024,6,30,23,59,59))
            currrent = timezone.make_aware(datetime(2024,6,30,0,0,0))
            task = Task(title='task1', due_at=due)
            task.save()

            self.assertFalse(task.is_overdue(currrent))

class TodoViewTestCase(TestCase):
    def test_index_get(self):
        client = Client()
        respose = Client.get('/')

        self.assertEqual(respose.status_code, 200)
        self.assertEqual(respose.templates[0].name, 'todo/index.html')
        self.assertEqual(len(respose.context['tasks']), 0)
        
    def test_index_post(self):
        client = Client()
        data = {'title': 'Test Task', 'due_at': '2024-06-30 23:59:59'}
        response = client.post('/', data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, 'todo/index.html')
        self.assertEqual(len(response.context['tasks']), 1)