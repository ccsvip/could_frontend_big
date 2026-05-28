from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role


scrolling_text_access_migration = import_module('apps.resources.migrations.0020_scrolling_text_and_access_data')


class ScrollingTextAccessDataMigrationTests(TestCase):
    def test_seed_scrolling_text_access_data_assigns_view_to_regular_roles(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        scrolling_text_access_migration.seed_scrolling_text_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/resources').exists())
        self.assertTrue(role.menus.filter(key='/resources/scrolling-texts').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='resources.scrolling_texts.').values_list('code', flat=True),
            ['resources.scrolling_texts.view'],
        )

    def test_seed_scrolling_text_access_data_assigns_all_permissions_to_admin_role(self):
        role = Role.objects.create(name='管理员', code='admin')

        scrolling_text_access_migration.seed_scrolling_text_access_data(django_apps, None)

        self.assertCountEqual(
            role.permission_points.filter(code__startswith='resources.scrolling_texts.').values_list('code', flat=True),
            [
                'resources.scrolling_texts.view',
                'resources.scrolling_texts.create',
                'resources.scrolling_texts.update',
                'resources.scrolling_texts.delete',
            ],
        )
