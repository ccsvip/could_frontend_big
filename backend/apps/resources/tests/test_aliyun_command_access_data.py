from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role


aliyun_command_access_migration = import_module('apps.resources.migrations.0009_aliyun_command_access_data')


class AliyunCommandAccessDataMigrationTests(TestCase):
    def test_seed_aliyun_command_access_data_assigns_readonly_permission_to_existing_roles(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        aliyun_command_access_migration.seed_aliyun_command_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/commands/aliyun').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.aliyun.').values_list('code', flat=True),
            ['commands.aliyun.view'],
        )

    def test_seed_aliyun_command_access_data_assigns_view_permission_to_admin_role(self):
        role = Role.objects.create(name='管理员', code='admin')

        aliyun_command_access_migration.seed_aliyun_command_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/commands/aliyun').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.aliyun.').values_list('code', flat=True),
            ['commands.aliyun.view'],
        )

    def test_seed_aliyun_command_access_data_keeps_existing_commands_parent_menu(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        aliyun_command_access_migration.seed_aliyun_command_access_data(django_apps, None)

        parent = role.menus.get(key='/commands/aliyun').parent
        self.assertIsNotNone(parent)
        self.assertEqual(parent.key, '/commands')
