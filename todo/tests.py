from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections
from django.test import (
    Client,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import reverse
from django.utils import timezone

from todo.models import SubTask, Task
from todo.views import mark_task_done



class ResponsiveStylesTestCase(SimpleTestCase):
    def test_forms_use_single_column_at_smartphone_width(self):
        stylesheet_path = finders.find('todo/style.css')
        self.assertIsNotNone(stylesheet_path)

        with open(stylesheet_path, encoding='utf-8') as stylesheet:
            css = stylesheet.read()

        self.assertRegex(
            css,
            r'@media \(max-width: 560px\)\s*{[\s\S]*?'
            r'\.task-form,\s*\.filter-form,\s*\.subtask-form\s*'
            r'{\s*grid-template-columns: 1fr;',
        )

class SignUpViewTestCase(TestCase):
    def valid_data(self, **overrides):
        data = {
            'username': 'new-user',
            'password1': 'SafePassword-2026',
            'password2': 'SafePassword-2026',
        }
        data.update(overrides)
        return data

    def test_signup_get_renders_form(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/signup.html')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'アカウントを作成')

    def test_signup_success_creates_user_logs_in_and_redirects(self):
        response = self.client.post(reverse('signup'), self.valid_data())

        self.assertRedirects(response, reverse('index'))
        user = User.objects.get(username='new-user')
        self.assertTrue(user.check_password('SafePassword-2026'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_signup_rejects_duplicate_username(self):
        User.objects.create_user(username='new-user', password='Existing-2026')

        response = self.client.post(reverse('signup'), self.valid_data())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '同じユーザー名が既に登録済みです')
        self.assertEqual(User.objects.filter(username='new-user').count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signup_rejects_invalid_password(self):
        response = self.client.post(
            reverse('signup'),
            self.valid_data(password1='123', password2='123'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'このパスワードは短すぎます')
        self.assertFalse(User.objects.filter(username='new-user').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_signup_empty_post_shows_required_errors(self):
        response = self.client.post(reverse('signup'), {})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].is_bound)
        self.assertFormError(response.context['form'], 'username', 'このフィールドは必須です。')
        self.assertFormError(response.context['form'], 'password1', 'このフィールドは必須です。')
        self.assertFormError(response.context['form'], 'password2', 'このフィールドは必須です。')
        self.assertEqual(User.objects.count(), 0)

    def test_signup_rejects_post_without_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(reverse('signup'), self.valid_data())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='new-user').exists())

    def test_authenticated_user_is_redirected_from_signup(self):
        user = User.objects.create_user(username='member', password='Password-2026')
        self.client.force_login(user)

        get_response = self.client.get(reverse('signup'))
        post_response = self.client.post(reverse('signup'), self.valid_data())

        self.assertRedirects(get_response, reverse('index'))
        self.assertRedirects(post_response, reverse('index'))
        self.assertFalse(User.objects.filter(username='new-user').exists())

    def test_login_page_links_to_signup(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, f'href="{reverse("signup")}"')


class TaskModelTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password')

    def create_task(self, **kwargs):
        kwargs.setdefault('owner', self.owner)
        return Task.objects.create(**kwargs)

    def test_create_task_with_management_fields(self):
        due = timezone.make_aware(datetime(2026, 7, 31, 23, 59))
        task = self.create_task(
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
        task = self.create_task(title='デフォルト値の確認')
        self.assertEqual(task.tag, '')
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)
        self.assertEqual(task.category, Task.Category.OTHER)
        self.assertEqual(task.recurrence, Task.RECURRENCE_NONE)
        self.assertIsNone(task.due_at)

    def test_delete_task_deletes_subtasks(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        task.delete()
        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_next_due_at_daily(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = Task(
            owner=self.owner,
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
            owner=self.owner,
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
            owner=self.owner,
            title='task1',
            recurrence=Task.RECURRENCE_MONTHLY,
            due_at=due,
        )
        self.assertEqual(
            task.next_due_at(),
            timezone.make_aware(datetime(2024, 2, 29, 10, 0)),
        )

    def test_monthly_recurrence_returns_to_original_day_after_short_month(self):
        january_due = timezone.make_aware(datetime(2024, 1, 31, 10, 0))
        january_task = self.create_task(
            title='month end',
            recurrence=Task.RECURRENCE_MONTHLY,
            recurrence_day=31,
            due_at=january_due,
        )

        february_task = january_task.create_next_occurrence()
        march_task = february_task.create_next_occurrence()

        self.assertEqual(
            february_task.due_at,
            timezone.make_aware(datetime(2024, 2, 29, 10, 0)),
        )
        self.assertEqual(february_task.recurrence_day, 31)
        self.assertEqual(
            march_task.due_at,
            timezone.make_aware(datetime(2024, 3, 31, 10, 0)),
        )
        self.assertEqual(march_task.recurrence_day, 31)

    def test_monthly_recurrence_handles_non_leap_year_and_year_boundary(self):
        december_due = timezone.make_aware(datetime(2024, 12, 31, 10, 0))
        december_task = self.create_task(
            title='year end',
            recurrence=Task.RECURRENCE_MONTHLY,
            recurrence_day=31,
            due_at=december_due,
        )

        january_task = december_task.create_next_occurrence()
        february_task = january_task.create_next_occurrence()
        march_task = february_task.create_next_occurrence()

        self.assertEqual(
            january_task.due_at,
            timezone.make_aware(datetime(2025, 1, 31, 10, 0)),
        )
        self.assertEqual(
            february_task.due_at,
            timezone.make_aware(datetime(2025, 2, 28, 10, 0)),
        )
        self.assertEqual(
            march_task.due_at,
            timezone.make_aware(datetime(2025, 3, 31, 10, 0)),
        )

    def test_create_next_occurrence_inherits_management_fields(self):
        due = timezone.make_aware(datetime(2026, 7, 1, 10, 0))
        task = self.create_task(
            title='task1',
            tag='study',
            description='次回にも引き継ぐメモ',
            priority=Task.Priority.HIGH,
            category=Task.Category.UNIVERSITY,
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )
        next_task = task.create_next_occurrence()
        self.assertEqual(next_task.owner, self.owner)
        self.assertEqual(next_task.title, 'task1')
        self.assertEqual(next_task.tag, 'study')
        self.assertEqual(next_task.description, '次回にも引き継ぐメモ')
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
        task = self.create_task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=due,
        )
        first = task.create_next_occurrence()
        second = task.create_next_occurrence()
        self.assertEqual(first, second)
        self.assertEqual(Task.objects.exclude(pk=task.pk).count(), 1)

    def test_database_rejects_second_next_occurrence_for_same_source(self):
        task = self.create_task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
        )
        task.create_next_occurrence()

        with self.assertRaises(IntegrityError):
            Task.objects.create(
                owner=self.owner,
                title='duplicate',
                recurrence_source=task,
            )

    def test_is_overdue_future(self):
        due = timezone.make_aware(datetime(2026, 7, 31, 23, 59))
        current = timezone.make_aware(datetime(2026, 7, 30, 0, 0))
        task = self.create_task(title='task1', due_at=due)
        self.assertFalse(task.is_overdue(current))

    def test_is_overdue_past(self):
        due = timezone.make_aware(datetime(2026, 7, 30, 23, 59))
        current = timezone.make_aware(datetime(2026, 7, 31, 0, 0))
        task = self.create_task(title='task1', due_at=due)
        self.assertTrue(task.is_overdue(current))

    def test_is_overdue_without_due_date(self):
        current = timezone.make_aware(datetime(2026, 7, 31, 0, 0))
        task = self.create_task(title='task1')
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
            'description': 'タスクのメモ',
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

    def test_all_pages_set_mobile_viewport(self):
        self.client.logout()
        login_response = self.client.get('/login/')
        self.client.force_login(self.user)
        task = self.create_task(title='responsive task')
        responses = [
            login_response,
            self.client.get('/'),
            self.client.get('/dashboard/'),
            self.client.get('/{}/'.format(task.pk)),
            self.client.get('/{}/update'.format(task.pk)),
        ]

        for response in responses:
            with self.subTest(path=response.request['PATH_INFO']):
                self.assertContains(
                    response,
                    '<meta name="viewport" '
                    'content="width=device-width, initial-scale=1">',
                    count=1,
                )

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
        self.assertEqual(task.description, 'タスクのメモ')
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.category, Task.Category.UNIVERSITY)
        self.assertEqual(task.recurrence, Task.RECURRENCE_WEEKLY)

    def test_index_post_accepts_empty_due_date_tag_and_description(self):
        response = self.client.post(
            '/',
            self.task_data(due_at='', tag='', description=''),
        )
        self.assertRedirects(response, '/')
        task = Task.objects.get()
        self.assertIsNone(task.due_at)
        self.assertEqual(task.tag, '')
        self.assertEqual(task.description, '')

    def test_index_post_rejects_empty_title(self):
        response = self.client.post('/', self.task_data(title=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)
        self.assertContains(response, 'このフィールドは必須です')

    def test_index_only_shows_own_tasks(self):
        own_task = self.create_task(title='own task')
        Task.objects.create(title='other task', owner=self.other_user)
        response = self.client.get('/')
        self.assertEqual(list(response.context['tasks']), [own_task])
        self.assertContains(response, 'own task')
        self.assertNotContains(response, 'other task')

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

    def test_dashboard_requires_login(self):
        self.client.logout()

        response = self.client.get('/dashboard/')

        self.assertRedirects(
            response,
            '/login/?next=/dashboard/',
            fetch_redirect_response=False,
        )

    def test_dashboard_groups_due_tasks_and_excludes_other_users(self):
        now = timezone.make_aware(datetime(2026, 7, 17, 12, 0))
        today = self.create_task(
            title='today task',
            due_at=timezone.make_aware(datetime(2026, 7, 17, 18, 0)),
        )
        overdue = self.create_task(
            title='overdue task',
            due_at=timezone.make_aware(datetime(2026, 7, 16, 18, 0)),
        )
        upcoming = self.create_task(
            title='upcoming task',
            due_at=timezone.make_aware(datetime(2026, 7, 20, 18, 0)),
        )
        self.create_task(title='without due date')
        self.create_task(
            title='completed overdue',
            status=Task.Status.DONE,
            due_at=timezone.make_aware(datetime(2026, 7, 15, 18, 0)),
        )
        Task.objects.create(
            owner=self.other_user,
            title='other user task',
            due_at=timezone.make_aware(datetime(2026, 7, 17, 18, 0)),
        )

        with patch('todo.views.timezone.now', return_value=now):
            response = self.client.get('/dashboard/')

        self.assertEqual(list(response.context['today_tasks']), [today])
        self.assertEqual(list(response.context['overdue_tasks']), [overdue])
        self.assertEqual(list(response.context['upcoming_tasks']), [upcoming])
        self.assertNotContains(response, 'other user task')
        self.assertNotContains(response, 'completed overdue')

    def test_dashboard_status_counts_and_completion_rate(self):
        self.create_task(title='todo', status=Task.Status.TODO)
        self.create_task(title='doing', status=Task.Status.DOING)
        self.create_task(title='done one', status=Task.Status.DONE)
        self.create_task(title='done two', status=Task.Status.DONE)

        response = self.client.get('/dashboard/')

        counts = {
            item['value']: item['count']
            for item in response.context['status_summary']
        }
        self.assertEqual(counts, {'todo': 1, 'doing': 1, 'done': 2})
        self.assertEqual(response.context['total_count'], 4)
        self.assertEqual(response.context['completion_rate'], 50)

    def test_detail_includes_tag_recurrence_and_subtasks(self):
        task = self.create_task(
            title='task1',
            tag='study',
            description='詳細画面に表示するメモ',
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
        self.assertContains(response, '詳細画面に表示するメモ')
        self.assertContains(response, '毎日')
        self.assertContains(response, 'subtask1')

    def test_detail_displays_placeholder_without_description(self):
        task = self.create_task(
            title='task without description',
            due_at=timezone.make_aware(datetime(2026, 7, 31, 23, 59)),
        )

        response = self.client.get('/{}/'.format(task.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '説明')
        self.assertContains(response, '未設定', count=1)

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
            description='編集後のメモ',
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
        self.assertEqual(task.description, '編集後のメモ')
        self.assertEqual(task.status, Task.Status.DOING)
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.category, Task.Category.PERSONAL)
        self.assertEqual(task.recurrence, Task.RECURRENCE_MONTHLY)

    def test_update_due_date_resets_notification_and_allows_resend(self):
        self.user.email = 'alice@example.com'
        self.user.save(update_fields=['email'])
        original_due = timezone.now() + timezone.timedelta(hours=6)
        task = self.create_task(
            title='task1',
            due_at=original_due,
            notified_at=timezone.now(),
        )
        new_due = timezone.now() + timezone.timedelta(hours=12)
        response = self.client.post(
            '/{}/update'.format(task.pk),
            self.task_data(due_at=new_due.strftime('%Y-%m-%dT%H:%M')),
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertIsNone(task.notified_at)

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
        ):
            call_command('notify_due_tasks')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Test Task', mail.outbox[0].body)

    def test_update_without_due_date_change_keeps_notification(self):
        due = timezone.now().replace(second=0, microsecond=0)
        due += timezone.timedelta(hours=12)
        notified_at = timezone.now()
        task = self.create_task(
            title='task1',
            due_at=due,
            notified_at=notified_at,
        )
        response = self.client.post(
            '/{}/update'.format(task.pk),
            self.task_data(
                title='renamed',
                due_at=timezone.localtime(due).strftime('%Y-%m-%dT%H:%M'),
            ),
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.notified_at, notified_at)

    def test_update_removing_due_date_clears_notification(self):
        task = self.create_task(
            title='task1',
            due_at=timezone.now() + timezone.timedelta(hours=12),
            notified_at=timezone.now(),
        )
        response = self.client.post(
            '/{}/update'.format(task.pk),
            self.task_data(due_at=''),
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertIsNone(task.due_at)
        self.assertIsNone(task.notified_at)

    def test_update_monthly_due_date_updates_recurrence_day(self):
        task = self.create_task(
            title='monthly task',
            recurrence=Task.RECURRENCE_MONTHLY,
            recurrence_day=31,
            due_at=timezone.make_aware(datetime(2026, 7, 31, 10, 0)),
        )
        response = self.client.post(
            '/{}/update'.format(task.pk),
            self.task_data(
                recurrence=Task.RECURRENCE_MONTHLY,
                due_at='2026-08-15T10:00',
            ),
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        task.refresh_from_db()
        self.assertEqual(task.recurrence_day, 15)

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

    def test_complete_rolls_back_when_next_occurrence_creation_fails(self):
        task = self.create_task(
            title='task1',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
        )

        with patch.object(
            Task,
            'create_next_occurrence',
            side_effect=RuntimeError('creation failed'),
        ):
            with self.assertRaises(RuntimeError):
                mark_task_done(task)

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertFalse(Task.objects.filter(recurrence_source=task).exists())

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

    def test_toggle_subtask_post_returns_completed_subtask_to_incomplete(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(
            task=task,
            title='subtask1',
            completed=True,
        )

        response = self.client.post(
            '/{}/subtasks/{}/toggle/'.format(task.pk, subtask.pk)
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        subtask.refresh_from_db()
        self.assertFalse(subtask.completed)

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

    def test_delete_subtask_without_csrf_token_is_forbidden(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk)
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_delete_subtask_with_csrf_token_succeeds(self):
        task = self.create_task(title='task1')
        subtask = SubTask.objects.create(task=task, title='subtask1')
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        detail_response = csrf_client.get('/{}/'.format(task.pk))
        csrf_token = detail_response.cookies['csrftoken'].value

        response = csrf_client.post(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk),
            {'csrfmiddlewaretoken': csrf_token},
        )

        self.assertRedirects(response, '/{}/'.format(task.pk))
        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_delete_subtask_rejects_other_users_task(self):
        task = Task.objects.create(title='other', owner=self.other_user)
        subtask = SubTask.objects.create(task=task, title='subtask1')
        response = self.client.post(
            '/{}/subtasks/{}/delete/'.format(task.pk, subtask.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_create_task_with_description(self):
        task = self.create_task(
            title='Task with Desc',
            description='This is a memo.',
        )
        saved_task = Task.objects.get(pk=task.pk)
        self.assertEqual(saved_task.description, 'This is a memo.')

    def test_create_task_without_description(self):
        task = self.create_task(title='No Desc Task')
        saved_task = Task.objects.get(pk=task.pk)
        self.assertIn(saved_task.description, [None, ''])



@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
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

    def test_notify_due_tasks_skips_done_and_far_tasks(self):
        self.create_task(
            title='done',
            status=Task.Status.DONE,
            due_at=timezone.now() + timezone.timedelta(hours=12),
        )
        self.create_task(
            title='far',
            due_at=timezone.now() + timezone.timedelta(days=3),
        )
        call_command('notify_due_tasks')
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_due_tasks_does_not_send_duplicates(self):
        task = self.create_task(
            title='task1',
            due_at=timezone.now() + timezone.timedelta(hours=12),
        )
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
                'status': legacy_task.status,
                'priority': legacy_task.priority,
                'category': legacy_task.category,
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


@skipUnlessDBFeature('has_select_for_update')
class RecurringTaskConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_completion_creates_one_next_occurrence(self):
        owner = User.objects.create_user(username='owner', password='password')
        task = Task.objects.create(
            owner=owner,
            title='concurrent task',
            recurrence=Task.RECURRENCE_DAILY,
            due_at=timezone.make_aware(datetime(2026, 7, 1, 10, 0)),
        )
        barrier = Barrier(2)

        def complete_task():
            close_old_connections()
            local_task = Task.objects.get(pk=task.pk)
            barrier.wait()
            mark_task_done(local_task)
            close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(complete_task) for _ in range(2)]
            for future in futures:
                future.result()

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)
        self.assertEqual(Task.objects.filter(recurrence_source=task).count(), 1)
