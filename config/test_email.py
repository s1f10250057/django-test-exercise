import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionEmailSettingsTestCase(SimpleTestCase):
    def test_production_reads_smtp_environment(self):
        command = (
            'from django.conf import settings; '
            'print(settings.EMAIL_BACKEND); '
            'print(settings.EMAIL_HOST); '
            'print(settings.EMAIL_PORT); '
            'print(settings.EMAIL_USE_TLS); '
            'print(settings.DEFAULT_FROM_EMAIL)'
        )
        result = subprocess.run(
            [sys.executable, 'manage.py', 'shell', '-c', command],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env={
                **os.environ,
                'DATABASE_URL': 'sqlite:///:memory:',
                'DEFAULT_FROM_EMAIL': 'tasks@example.com',
                'DJANGO_SETTINGS_MODULE': 'config.production',
                'EMAIL_HOST': 'smtp.example.com',
                'EMAIL_HOST_PASSWORD': 'test-password',
                'EMAIL_HOST_USER': 'smtp-user',
                'EMAIL_PORT': '2525',
                'EMAIL_USE_TLS': 'true',
                'RENDER_EXTERNAL_HOSTNAME': 'example.com',
                'SECRET_KEY': 'test-secret-key-for-email-settings',
            },
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().splitlines()[-5:]
        self.assertEqual(
            values,
            [
                'django.core.mail.backends.smtp.EmailBackend',
                'smtp.example.com',
                '2525',
                'True',
                'tasks@example.com',
            ],
        )
