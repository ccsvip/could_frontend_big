from django.db import migrations


AGENT_APPLICATION_TENANT_PERMISSION_CODES = [
    'agent_applications.view',
    'agent_applications.create',
    'agent_applications.update',
]


def seed_agent_application_tenant_access(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Tenant = apps.get_model('tenants', 'Tenant')

    application_menu = Menu.objects.filter(key='/applications').first()
    if application_menu is None:
        return

    tenant_permissions = list(
        PermissionPoint.objects.filter(code__in=AGENT_APPLICATION_TENANT_PERMISSION_CODES)
    )
    for tenant in Tenant.objects.all():
        tenant.menus.add(application_menu)
        if tenant_permissions:
            tenant.permission_points.add(*tenant_permissions)


def unseed_agent_application_tenant_access(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Tenant = apps.get_model('tenants', 'Tenant')

    application_menu = Menu.objects.filter(key='/applications').first()
    tenant_permissions = list(
        PermissionPoint.objects.filter(code__in=AGENT_APPLICATION_TENANT_PERMISSION_CODES)
    )
    for tenant in Tenant.objects.all():
        if application_menu is not None:
            tenant.menus.remove(application_menu)
        if tenant_permissions:
            tenant.permission_points.remove(*tenant_permissions)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0011_agentapplication_chatconversation_application_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_agent_application_tenant_access, unseed_agent_application_tenant_access),
    ]
