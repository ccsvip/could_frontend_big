from django.db import migrations


MENUS = [
    {
        'key': '/commands/groups',
        'path': '/commands/groups',
        'name': '指令管理',
        'icon': 'ThunderboltOutlined',
        'sort_order': 1,
    },
    {
        'key': '/commands/control',
        'path': '/commands/control',
        'name': '控制指令',
        'icon': 'CloudOutlined',
        'sort_order': 2,
    },
    {
        'key': '/commands/tasks',
        'path': '/commands/tasks',
        'name': '任务指令',
        'icon': 'ThunderboltOutlined',
        'sort_order': 3,
    },
    {
        'key': '/commands/points',
        'path': '/commands/points',
        'name': '点位管理',
        'icon': 'EnvironmentOutlined',
        'sort_order': 4,
    },
    {
        'key': '/commands/export',
        'path': '/commands/export',
        'name': '导出管理',
        'icon': 'ExportOutlined',
        'sort_order': 5,
    },
]

PERMISSIONS = [
    ('commands.groups.view', '查看指令管理', 'commands_groups'),
    ('commands.groups.create', '新增指令管理', 'commands_groups'),
    ('commands.groups.update', '修改指令管理', 'commands_groups'),
    ('commands.groups.delete', '删除指令管理', 'commands_groups'),
    ('commands.control.view', '查看控制指令', 'commands_control'),
    ('commands.control.create', '新增控制指令', 'commands_control'),
    ('commands.control.update', '修改控制指令', 'commands_control'),
    ('commands.control.delete', '删除控制指令', 'commands_control'),
    ('commands.tasks.view', '查看任务指令', 'commands_tasks'),
    ('commands.tasks.create', '新增任务指令', 'commands_tasks'),
    ('commands.tasks.update', '修改任务指令', 'commands_tasks'),
    ('commands.tasks.delete', '删除任务指令', 'commands_tasks'),
    ('commands.points.view', '查看点位', 'commands_points'),
    ('commands.points.create', '新增点位', 'commands_points'),
    ('commands.points.update', '修改点位', 'commands_points'),
    ('commands.points.delete', '删除点位', 'commands_points'),
    ('commands.export.view', '查看导出管理', 'commands_export'),
    ('commands.export.download', '下载导出文件', 'commands_export'),
]

LEGACY_MENU_KEYS = [
    '/commands/types',
    '/commands/types/control',
    '/commands/types/navigation',
    '/commands/types/central',
    '/commands/navigation',
    '/commands/point-resources',
]

LEGACY_PERMISSION_PREFIXES = [
    'commands.navigation.',
    'commands.point_resources.',
    'commands.central.',
]

LEGACY_PERMISSION_CODES = [
    'commands.control.import',
    'commands.control.export',
]


def seed_backend_management_flow_access(apps, schema_editor):
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
    Menu.objects.filter(key__in=LEGACY_MENU_KEYS).delete()

    created_menus = []
    for menu in MENUS:
        item, _ = Menu.objects.update_or_create(
            key=menu['key'],
            defaults={
                'name': menu['name'],
                'path': menu['path'],
                'icon': menu['icon'],
                'sort_order': menu['sort_order'],
                'is_active': True,
                'parent_id': command_parent.id,
            },
        )
        created_menus.append(item)

    for prefix in LEGACY_PERMISSION_PREFIXES:
        PermissionPoint.objects.filter(code__startswith=prefix).delete()
    PermissionPoint.objects.filter(code__in=LEGACY_PERMISSION_CODES).delete()

    created_permissions = []
    for code, name, module in PERMISSIONS:
        permission, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': name,
                'is_active': True,
            },
        )
        created_permissions.append(permission)

    view_permissions = [permission for permission in created_permissions if permission.code.endswith('.view')]
    for role in Role.objects.all():
        role.menus.add(command_parent, *created_menus)
        if role.code == 'admin':
            role.permission_points.add(*created_permissions)
        else:
            role.permission_points.add(*view_permissions)


def unseed_backend_management_flow_access(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    Menu.objects.filter(key__in=[menu['key'] for menu in MENUS]).delete()
    PermissionPoint.objects.filter(code__in=[item[0] for item in PERMISSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0015_backend_management_flow_schema'),
    ]

    operations = [
        migrations.RunPython(seed_backend_management_flow_access, unseed_backend_management_flow_access),
    ]
