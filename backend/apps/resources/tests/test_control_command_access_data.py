from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role


control_command_access_migration = import_module('apps.resources.migrations.0008_controlcommand_and_access_data')


class ControlCommandAccessDataMigrationTests(TestCase):
    def test_seed_control_command_access_data_assigns_readonly_permissions_to_existing_roles(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        control_command_access_migration.seed_control_command_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/commands/control').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.control.').values_list('code', flat=True),
            ['commands.control.view', 'commands.control.export'],
        )

    def test_seed_control_command_access_data_assigns_full_permissions_to_admin_role(self):
        role = Role.objects.create(name='管理员', code='admin')

        control_command_access_migration.seed_control_command_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/commands/control').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.control.').values_list('code', flat=True),
            [
                'commands.control.view',
                'commands.control.create',
                'commands.control.update',
                'commands.control.delete',
                'commands.control.import',
                'commands.control.export',
            ],
        )
