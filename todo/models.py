from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import calendar

# Create your models here.


class Task(models.Model):
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
        null=True,
        blank=True,
        related_name='tasks',
    )
    title = models.CharField(max_length=100)
    tag = models.CharField(max_length=50, blank=True)
    completed = models.BooleanField(default=False)
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE)
    posted_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    def is_overdue(self, dt):
        if self.due_at is None:
            return False
        return self.due_at < dt

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
            day = min(self.due_at.day, calendar.monthrange(year, month)[1])
            return self.due_at.replace(year=year, month=month, day=day)
        return None

    def create_next_occurrence(self):
        due_at = self.next_due_at()
        if due_at is None:
            return None
        return Task.objects.create(
            owner=self.owner,
            title=self.title,
            tag=self.tag,
            recurrence=self.recurrence,
            due_at=due_at,
        )


class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title = models.CharField(max_length=100)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
