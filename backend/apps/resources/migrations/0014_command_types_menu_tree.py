from django.db import migrations


CENTRAL_PERMISSION = {
    'name': '查看中控',
    'code': 'commands.central.view',
    'module': 'commands_central',
    'description': '允许查看中控页面',
}


def upsert_menu(
    Menu,
    *,
    key,
    path,
    name,
    icon,
    sort_order,
    parent_id,
    legacy_keys=(),
):
    menu = Menu.objects.filter(key=key).first() or Menu.objects.filter(path=path).first()
    legacy_menus = list(Menu.objects.filter(key__in=legacy_keys))

    if menu is None and legacy_menus:
        menu = legacy_menus[0]

    defaults = {
        'name': name,
        'key': key,
        'path': path,
        'icon': icon,
        'sort_order': sort_order,
        'is_active': True,
        'parent_id': parent_id,
    }

    if menu is None:
        menu = Menu.objects.create(**defaults)
    else:
        for field, value in defaults.items():
            setattr(menu, field, value)
        menu.save(update_fields=list(defaults.keys()))

    for legacy_menu in legacy_menus:
        if legacy_menu.id == menu.id:
            continue
        for role in legacy_menu.roles.all():
            role.menus.add(menu)
        legacy_menu.delete()

    return menu


def seed_command_types_access_data(apps, schema_editor):
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

    command_types_menu, _ = Menu.objects.update_or_create(
        key='/commands/types',
        defaults={
            'name': '指令类型',
            'path': '/commands/types',
            'icon': 'ThunderboltOutlined',
            'sort_order': 41,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    upsert_menu(
        Menu,
        key='/commands/types/control',
        path='/commands/types/control',
        name='控制指令',
        icon='ThunderboltOutlined',
        sort_order=1,
        parent_id=command_types_menu.id,
        legacy_keys=('/commands/control',),
    )
    upsert_menu(
        Menu,
        key='/commands/types/navigation',
        path='/commands/types/navigation',
        name='导航指令',
        icon='EnvironmentOutlined',
        sort_order=2,
        parent_id=command_types_menu.id,
        legacy_keys=('/commands/navigation',),
    )
    central_menu = upsert_menu(
        Menu,
        key='/commands/types/central',
        path='/commands/types/central',
        name='中控',
        icon='CloudOutlined',
        sort_order=3,
        parent_id=command_types_menu.id,
    )

    Menu.objects.filter(key='/commands/point-resources').update(parent_id=command_parent.id)
    Menu.objects.filter(key='/commands/points').update(parent_id=command_parent.id)

    central_view_permission, _ = PermissionPoint.objects.update_or_create(
        code=CENTRAL_PERMISSION['code'],
        defaults={
            'name': CENTRAL_PERMISSION['name'],
            'module': CENTRAL_PERMISSION['module'],
            'description': CENTRAL_PERMISSION['description'],
            'is_active': True,
        },
    )

    for role in Role.objects.all():
        role.menus.add(central_menu)
        role.permission_points.add(central_view_permission)


def unseed_command_types_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    command_parent = Menu.objects.filter(key='/commands').first()

    control_menu = Menu.objects.filter(key='/commands/types/control').first()
    if control_menu:
        control_menu.key = '/commands/control'
        control_menu.path = '/commands/control'
        control_menu.sort_order = 41
        control_menu.parent_id = command_parent.id if command_parent else None
        control_menu.save(update_fields=['key', 'path', 'sort_order', 'parent_id'])

    navigation_menu = Menu.objects.filter(key='/commands/types/navigation').first()
    if navigation_menu:
        navigation_menu.key = '/commands/navigation'
        navigation_menu.path = '/commands/navigation'
        navigation_menu.sort_order = 42
        navigation_menu.parent_id = command_parent.id if command_parent else None
        navigation_menu.save(update_fields=['key', 'path', 'sort_order', 'parent_id'])

    Menu.objects.filter(key='/commands/types/central').delete()
    Menu.objects.filter(key='/commands/types').delete()
    PermissionPoint.objects.filter(code=CENTRAL_PERMISSION['code']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0013_remove_aliyun_command_menu'),
    ]

    operations = [
        migrations.RunPython(seed_command_types_access_data, unseed_command_types_access_data),
    ]
