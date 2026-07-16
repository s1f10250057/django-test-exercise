import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionStaticFilesTestCase(SimpleTestCase):
    def production_env(self):
        return {
            **os.environ,
            'DATABASE_URL': 'sqlite:///:memory:',
            'DJANGO_SETTINGS_MODULE': 'config.production',
            'RENDER_EXTERNAL_HOSTNAME': 'example.com',
            'SECRET_KEY': 'test-secret-key-for-staticfiles',
        }

    def run_manage(self, *args):
        return subprocess.run(
            [sys.executable, 'manage.py', *args],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=self.production_env(),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_uses_whitenoise_manifest_storage(self):
        result = self.run_manage(
            'shell',
            '-c',
            'from django.conf import settings; '
            'print(settings.STORAGES["staticfiles"]["BACKEND"]); '
            'print(settings.MIDDLEWARE[1])',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
            result.stdout,
        )
        self.assertIn(
            'whitenoise.middleware.WhiteNoiseMiddleware',
            result.stdout,
        )

    def test_collectstatic_dry_run_with_production_settings(self):
        result = self.run_manage(
            'collectstatic',
            '--dry-run',
            '--no-input',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
