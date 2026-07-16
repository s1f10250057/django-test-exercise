from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from todo.models import Task


class Command(BaseCommand):
    help = 'Send reminder email for incomplete tasks that are due soon.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1)
        parser.add_argument('--owner', default=None)

    def handle(self, *args, **options):
        now = timezone.now()
        due_until = now + timezone.timedelta(days=options['days'])
        owner = None
        if options['owner']:
            user_model = get_user_model()
            try:
                owner = user_model.objects.get_by_natural_key(options['owner'])
            except user_model.DoesNotExist as exc:
                raise CommandError('Owner does not exist.') from exc

        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')

        tasks = Task.objects.filter(
            completed=False,
            due_at__isnull=False,
            due_at__gte=now,
            due_at__lte=due_until,
            notified_at__isnull=True,
        ).select_related('owner')
        if owner is not None:
            tasks = tasks.filter(owner=owner)
        tasks = tasks.order_by('due_at')

        count = 0
        skipped = 0
        for task in tasks:
            recipient = (task.owner.email or '').strip()
            if not recipient:
                skipped += 1
                continue
            send_mail(
                'Task due soon',
                '{} is due at {}.'.format(task.title, task.due_at),
                sender,
                [recipient],
            )
            task.notified_at = now
            task.save(update_fields=['notified_at'])
            count += 1

        self.stdout.write('Sent {} notification(s).'.format(count))
        if skipped:
            self.stdout.write('Skipped {} task(s) without an owner email.'.format(skipped))
