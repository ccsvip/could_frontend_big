from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role


model_access_migration = import_module('apps.resources.migrations.0006_modelasset_and_access_data')


class ModelAssetAccessDataMigrationTests(TestCase):
    def test_seed_model_access_data_assigns_menu_and_permissions_to_existing_roles(self):
        role = Role.objects.create(name='模型运营', code='model_operator')

        model_access_migration.seed_model_access_data(django_apps, None)

        self.assertTrue(role.menus.filter(key='/resources/models').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='resources.models.').values_list('code', flat=True),
            [
                'resources.models.view',
                'resources.models.create',
                'resources.models.update',
                'resources.models.delete',
            ],
        )
