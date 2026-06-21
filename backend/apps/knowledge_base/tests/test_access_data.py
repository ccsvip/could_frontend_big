from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounts.models import Role
from apps.tenants.models import Tenant


knowledge_base_migration = import_module('apps.knowledge_base.migrations.0001_initial')
knowledge_base_menu_migration = import_module('apps.knowledge_base.migrations.0005_knowledgebase_document_relation_and_menu')


class KnowledgeBaseAccessDataMigrationTests(TestCase):
    def test_seed_knowledge_base_access_data_assigns_menu_and_permissions_to_existing_roles(self):
        role = Role.objects.create(name='知识库运营', code='knowledge_base_operator')

        knowledge_base_migration.seed_knowledge_base_access_data(django_apps, None)
        knowledge_base_menu_migration.move_knowledge_base_menu(django_apps, None)

        self.assertTrue(role.menus.filter(key='/ai-models/knowledge-base').exists())
        self.assertFalse(role.menus.filter(key='/knowledge-base').exists())
        self.assertCountEqual(
            role.permission_points.filter(code__startswith='knowledge_base.').values_list('code', flat=True),
            [
                'knowledge_base.view',
                'knowledge_base.upload',
                'knowledge_base.download',
                'knowledge_base.bulk_download',
            ],
        )

    def test_move_knowledge_base_menu_assigns_menu_and_permissions_to_existing_tenants(self):
        tenant = Tenant.objects.create(name='知识库公司', code='knowledge-tenant')

        knowledge_base_migration.seed_knowledge_base_access_data(django_apps, None)
        knowledge_base_menu_migration.move_knowledge_base_menu(django_apps, None)

        self.assertTrue(tenant.menus.filter(key='/ai-models/knowledge-base').exists())
        self.assertCountEqual(
            tenant.permission_points.filter(code__startswith='knowledge_base.').values_list('code', flat=True),
            [
                'knowledge_base.view',
                'knowledge_base.upload',
                'knowledge_base.download',
                'knowledge_base.bulk_download',
            ],
        )

