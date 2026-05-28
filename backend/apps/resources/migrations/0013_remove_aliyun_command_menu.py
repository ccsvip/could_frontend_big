from django.db import migrations


def remove_aliyun_command_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code='commands.aliyun.view').delete()
    Menu.objects.filter(key='/commands/aliyun').delete()


def restore_aliyun_command_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    command_parent = Menu.objects.filter(key='/commands').first()
    aliyun_command_menu, _ = Menu.objects.update_or_create(
        key='/commands/aliyun',
        defaults={
            'name': '指令操作',
            'path': '/commands/aliyun',
            'icon': '',
            'sort_order': 43,
            'is_active': True,
            'parent_id': command_parent.id if command_parent else None,
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


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0012_point_workflow_steps'),
    ]

    operations = [
        migrations.RunPython(remove_aliyun_command_menu, restore_aliyun_command_menu),
    ]
