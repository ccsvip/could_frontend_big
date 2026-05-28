from django.db import migrations


def seed_aliyun_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    command_parent, _ = Menu.objects.update_or_create(
        key='/commands',
        defaults={
            'name': '指令管理',
            'path': '/commands',
            'icon': 'ThunderboltOutlined',
            'sort_order': 40,
            'is_active': True,
            'parent_id': None,
        },
    )

    aliyun_command_menu, _ = Menu.objects.update_or_create(
        key='/commands/aliyun',
        defaults={
            'name': '指令操作',
            'path': '/commands/aliyun',
            'icon': 'ThunderboltOutlined',
            'sort_order': 42,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    aliyun_view_permission, _ = PermissionPoint.objects.update_or_create(
        code='commands.aliyun.view',
        defaults={
            'name': '查看阿里云指令',
            'module': 'commands_aliyun',
            'description': '允许查看阿里云指令列表',
            'is_active': True,
        },
    )

    for role in Role.objects.all():
        role.menus.add(aliyun_command_menu)
        role.permission_points.add(aliyun_view_permission)


def unseed_aliyun_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code='commands.aliyun.view').delete()
    Menu.objects.filter(key='/commands/aliyun').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0008_controlcommand_and_access_data'),
    ]

    operations = [
        migrations.RunPython(seed_aliyun_command_access_data, unseed_aliyun_command_access_data),
    ]
