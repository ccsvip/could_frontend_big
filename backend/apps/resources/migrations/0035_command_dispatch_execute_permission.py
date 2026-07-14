from django.db import migrations


def seed_command_dispatch_permission(apps, schema_editor):
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    permission, _ = PermissionPoint.objects.update_or_create(
        code='commands.dispatch.execute',
        defaults={
            'name': '执行指令下发',
            'module': 'commands_dispatch',
            'description': '允许设备运行时通过语义判断下发控制指令',
            'is_active': True,
        },
    )
    for role in Role.objects.all():
        role.permission_points.add(permission)
    for tenant in Tenant.objects.all():
        tenant.permission_points.add(permission)


def unseed_command_dispatch_permission(apps, schema_editor):
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    PermissionPoint.objects.filter(code='commands.dispatch.execute').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0034_storage_backend_r2'),
    ]

    operations = [
        migrations.RunPython(seed_command_dispatch_permission, unseed_command_dispatch_permission),
    ]
