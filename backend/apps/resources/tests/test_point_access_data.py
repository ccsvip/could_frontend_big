from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Menu, PermissionPoint, Role


access_migration = import_module('apps.resources.migrations.0016_backend_management_flow_access')


class BackendManagementFlowAccessMigrationTests(TestCase):
    def test_seed_assigns_readonly_permissions_to_existing_non_admin_roles(self):
        role = Role.objects.create(name='资源运营', code='resource_operator')

        access_migration.seed_backend_management_flow_access(django_apps, None)

        self.assertTrue(role.menus.filter(key='/commands/groups').exists())
        self.assertTrue(role.menus.filter(key='/commands/control').exists())
        self.assertTrue(role.menus.filter(key='/commands/tasks').exists())
        self.assertTrue(role.menus.filter(key='/commands/points').exists())
        self.assertTrue(role.menus.filter(key='/commands/export').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.').values_list('code', flat=True),
            [
                'commands.groups.view',
                'commands.control.view',
                'commands.tasks.view',
                'commands.points.view',
                'commands.export.view',
            ],
        )

    def test_seed_assigns_full_permissions_to_admin_and_removes_legacy_access(self):
        PermissionPoint.objects.create(code='commands.navigation.view', name='旧导航', module='commands_navigation')
        PermissionPoint.objects.create(code='commands.point_resources.view', name='旧点位资源', module='commands_point_resources')
        PermissionPoint.objects.create(code='commands.central.view', name='旧中控', module='commands_central')
        PermissionPoint.objects.create(code='commands.control.export', name='旧导出', module='commands_control')
        Menu.objects.create(key='/commands/navigation', path='/commands/navigation', name='旧导航')
        Menu.objects.create(key='/commands/point-resources', path='/commands/point-resources', name='旧点位资源')
        role = Role.objects.create(name='管理员', code='admin')

        access_migration.seed_backend_management_flow_access(django_apps, None)

        self.assertFalse(Menu.objects.filter(key='/commands/navigation').exists())
        self.assertFalse(Menu.objects.filter(key='/commands/point-resources').exists())
        self.assertFalse(PermissionPoint.objects.filter(code__startswith='commands.navigation.').exists())
        self.assertFalse(PermissionPoint.objects.filter(code__startswith='commands.point_resources.').exists())
        self.assertFalse(PermissionPoint.objects.filter(code__startswith='commands.central.').exists())
        self.assertFalse(PermissionPoint.objects.filter(code='commands.control.export').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='commands.').values_list('code', flat=True),
            [item[0] for item in access_migration.PERMISSIONS],
        )

    def test_unseed_removes_new_child_menus_but_keeps_commands_parent(self):
        access_migration.seed_backend_management_flow_access(django_apps, None)

        access_migration.unseed_backend_management_flow_access(django_apps, None)

        self.assertTrue(Menu.objects.filter(key='/commands').exists())
        self.assertFalse(Menu.objects.filter(key='/commands/groups').exists())
        self.assertFalse(Menu.objects.filter(key='/commands/control').exists())
        self.assertFalse(Menu.objects.filter(key='/commands/tasks').exists())
        self.assertFalse(Menu.objects.filter(key='/commands/export').exists())
