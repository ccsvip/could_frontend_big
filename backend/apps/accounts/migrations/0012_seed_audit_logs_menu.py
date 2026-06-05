from django.db import migrations


def seed_audit_logs_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    Menu.objects.update_or_create(
        key='/logs',
        defaults={
            'name': '日志管理',
            'path': '/logs',
            'icon': 'FileSearchOutlined',
            'audience': 'tenant_admin',
            'sort_order': 99,
            'is_active': True,
        },
    )
    PermissionPoint.objects.update_or_create(
        code='audit.logs.view',
        defaults={
            'name': '日志查看',
            'module': 'audit',
            'description': '允许查看和清空授权范围内的操作日志',
            'is_active': True,
        },
    )


def unseed_audit_logs_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Menu.objects.filter(key='/logs').delete()
    PermissionPoint.objects.filter(code='audit.logs.view').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_role_is_template_role_tenant_alter_role_code_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_audit_logs_menu, unseed_audit_logs_menu),
    ]
