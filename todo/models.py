import calendar
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = 'todo', '未着手'
        DOING = 'doing', '進行中'
        DONE = 'done', '完了'

    class Priority(models.TextChoices):
        HIGH = 'high', '高'
        MEDIUM = 'medium', '中'
        LOW = 'low', '低'

    class Category(models.TextChoices):
        UNIVERSITY = 'university', '大学'
        PERSONAL = 'personal', '個人'
        PART_TIME = 'part_time', 'アルバイト'
        OTHER = 'other', 'その他'

    RECURRENCE_NONE = 'none'
    RECURRENCE_DAILY = 'daily'
    RECURRENCE_WEEKLY = 'weekly'
    RECURRENCE_MONTHLY = 'monthly'
    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, 'None'),
        (RECURRENCE_DAILY, 'Daily'),
        (RECURRENCE_WEEKLY, 'Weekly'),
        (RECURRENCE_MONTHLY, 'Monthly'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    title = models.CharField(max_length=100)
    tag = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.TODO,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    recurrence = models.CharField(
        max_length=10,
        choices=RECURRENCE_CHOICES,
        default=RECURRENCE_NONE,
    )
    posted_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    recurrence_source = models.OneToOneField(
        'self',
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name='next_occurrence',
    )

    def is_overdue(self, dt):
        if self.due_at is None:
            return False
        return self.due_at < dt

    @property
    def recurrence_label(self):
        labels = {
            self.RECURRENCE_NONE: 'なし',
            self.RECURRENCE_DAILY: '毎日',
            self.RECURRENCE_WEEKLY: '毎週',
            self.RECURRENCE_MONTHLY: '毎月',
        }
        return labels[self.recurrence]

    def next_due_at(self):
        if self.due_at is None or self.recurrence == self.RECURRENCE_NONE:
            return None
        if self.recurrence == self.RECURRENCE_DAILY:
            return self.due_at + timedelta(days=1)
        if self.recurrence == self.RECURRENCE_WEEKLY:
            return self.due_at + timedelta(weeks=1)
        if self.recurrence == self.RECURRENCE_MONTHLY:
            year = self.due_at.year
            month = self.due_at.month + 1
            if month == 13:
                year += 1
                month = 1
            day = min(
                self.due_at.day,
                calendar.monthrange(year, month)[1],
            )
            return self.due_at.replace(year=year, month=month, day=day)
        return None

    def create_next_occurrence(self):
        due_at = self.next_due_at()
        if due_at is None:
            return None
        next_task, _ = Task.objects.get_or_create(
            recurrence_source=self,
            defaults={
                'owner': self.owner,
                'title': self.title,
                'tag': self.tag,
                'priority': self.priority,
                'category': self.category,
                'recurrence': self.recurrence,
                'due_at': due_at,
            },
        )
        return next_task


class SubTask(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='subtasks',
    )
    title = models.CharField(max_length=100)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
