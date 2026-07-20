import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionSecuritySettingsTestCase(SimpleTestCase):
    def test_production_https_settings_and_proxy_detection(self):
        command = (
            'from django.conf import settings; '
            'from django.test import RequestFactory; '
            'request = RequestFactory().get('
            '"/", HTTP_X_FORWARDED_PROTO="https"); '
            'print(settings.SECURE_SSL_REDIRECT); '
            'print(settings.SESSION_COOKIE_SECURE); '
            'print(settings.CSRF_COOKIE_SECURE); '
            'print(settings.SECURE_HSTS_SECONDS); '
            'print(request.is_secure())'
        )
        result = subprocess.run(
            [sys.executable, 'manage.py', 'shell', '-c', command],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env={
                **os.environ,
                'DATABASE_URL': 'sqlite:///:memory:',
                'DJANGO_SETTINGS_MODULE': 'config.production',
                'RENDER_EXTERNAL_HOSTNAME': 'example.com',
                'SECRET_KEY': 'test-secret-key-for-production-security',
            },
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().splitlines()[-5:]
        self.assertEqual(values, ['True', 'True', 'True', '3600', 'True'])
