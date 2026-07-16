from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from todo.models import Task


class Command(BaseCommand):
    help = 'Send reminder email for incomplete tasks that are due soon.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1)
        parser.add_argument('--recipient', default=None)

    def handle(self, *args, **options):
        now = timezone.now()
        due_until = now + timezone.timedelta(days=options['days'])
        recipient = options['recipient'] or getattr(settings, 'DEFAULT_NOTIFICATION_EMAIL', None)
        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')

        if not recipient:
            self.stdout.write('No recipient configured.')
            return

        tasks = Task.objects.filter(
            completed=False,
            due_at__isnull=False,
            due_at__gte=now,
            due_at__lte=due_until,
            notified_at__isnull=True,
        ).order_by('due_at')

        count = 0
        for task in tasks:
            send_mail(
                'Task due soon',
                '{} is due at {}.'.format(task.title, task.due_at),
                sender,
                [recipient],
            )
            task.notified_at = now
            task.save()
            count += 1

        self.stdout.write('Sent {} notification(s).'.format(count))
