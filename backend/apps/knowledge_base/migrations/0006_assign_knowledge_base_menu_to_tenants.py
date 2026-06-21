from django.db import migrations


def assign_knowledge_base_menu_to_tenants(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Tenant = apps.get_model('tenants', 'Tenant')

    menu = Menu.objects.filter(key='/ai-models/knowledge-base', is_active=True).first()
    if menu is None:
        return

    permission_points = list(PermissionPoint.objects.filter(code__startswith='knowledge_base.', is_active=True))
    for tenant in Tenant.objects.all():
        tenant.menus.add(menu)
        tenant.permission_points.add(*permission_points)


def unassign_knowledge_base_menu_from_tenants(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Tenant = apps.get_model('tenants', 'Tenant')

    menu = Menu.objects.filter(key='/ai-models/knowledge-base').first()
    permission_points = list(PermissionPoint.objects.filter(code__startswith='knowledge_base.'))
    for tenant in Tenant.objects.all():
        if menu is not None:
            tenant.menus.remove(menu)
        tenant.permission_points.remove(*permission_points)


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge_base', '0005_knowledgebase_document_relation_and_menu'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.RunPython(assign_knowledge_base_menu_to_tenants, unassign_knowledge_base_menu_from_tenants),
    ]
