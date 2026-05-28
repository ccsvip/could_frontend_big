from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role


voice_tone_access_migration = import_module('apps.resources.migrations.0003_voicetone_and_access_data')


class VoiceToneAccessDataMigrationTests(TestCase):
    def test_seed_voice_tone_access_data_assigns_menu_and_permissions_to_existing_roles(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        voice_tone_access_migration.seed_voice_tone_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/resources/voice-tones').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='resources.voice_tones.').values_list('code', flat=True),
            [
                'resources.voice_tones.view',
                'resources.voice_tones.create',
                'resources.voice_tones.update',
                'resources.voice_tones.delete',
            ],
        )
