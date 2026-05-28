from django.db import migrations, models


DEFAULT_NAVIGATION_COMMANDS = [
    {
        'name': '导航到充电桩',
        'command_code': 'navigate_to_cd',
        'trigger_text': '导航/导航到/带我去 充电/充电桩',
        'response_text': '正在前往充电桩',
        'sort': 1,
        'is_active': True,
        'is_visible': True,
    },
    {
        'name': '导航到前台',
        'command_code': 'navigate_to_ps',
        'trigger_text': '导航/导航到/带我去 前台',
        'response_text': '正在前往展厅',
        'sort': 2,
        'is_active': True,
        'is_visible': True,
    },
    {
        'name': '导航到展厅',
        'command_code': 'navigate_to_cp',
        'trigger_text': '导航/导航到/带我去 展厅',
        'response_text': '正在前往医院',
        'sort': 3,
        'is_active': True,
        'is_visible': True,
    },
    {
        'name': '导航到图书馆',
        'command_code': 'navigate_to_jj',
        'trigger_text': '导航/导航到/带我去 图书馆',
        'response_text': '正在前往图书馆',
        'sort': 4,
        'is_active': True,
        'is_visible': True,
    },
]


def seed_navigation_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    NavigationCommand = apps.get_model('resources', 'NavigationCommand')

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

    Menu.objects.filter(key='/commands/aliyun').update(sort_order=43)
    Menu.objects.filter(key='/commands/point-resources').update(sort_order=44)
    Menu.objects.filter(key='/commands/points').update(sort_order=45)

    navigation_menu, _ = Menu.objects.update_or_create(
        key='/commands/navigation',
        defaults={
            'name': '导航指令',
            'path': '/commands/navigation',
            'icon': 'EnvironmentOutlined',
            'sort_order': 42,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    permission_points = []
    for name, code, description in [
        ('查看导航指令', 'commands.navigation.view', '允许查看导航指令列表与详情'),
        ('创建导航指令', 'commands.navigation.create', '允许新增导航指令'),
        ('编辑导航指令', 'commands.navigation.update', '允许编辑导航指令'),
        ('删除导航指令', 'commands.navigation.delete', '允许删除导航指令'),
        ('导入导航指令', 'commands.navigation.import', '允许导入导航指令 JSON'),
        ('导出导航指令', 'commands.navigation.export', '允许导出导航指令 JSON'),
    ]:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': 'commands_navigation',
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(permission_point)

    readonly_codes = {'commands.navigation.view', 'commands.navigation.export'}
    readonly_permission_points = [item for item in permission_points if item.code in readonly_codes]

    for role in Role.objects.all():
        role.menus.add(navigation_menu)
        if role.code == 'admin':
            role.permission_points.add(*permission_points)
        else:
            role.permission_points.add(*readonly_permission_points)

    for item in DEFAULT_NAVIGATION_COMMANDS:
        NavigationCommand.objects.update_or_create(
            command_code=item['command_code'],
            defaults=item,
        )


def unseed_navigation_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    NavigationCommand = apps.get_model('resources', 'NavigationCommand')

    NavigationCommand.objects.filter(
        command_code__in=[item['command_code'] for item in DEFAULT_NAVIGATION_COMMANDS]
    ).delete()
    PermissionPoint.objects.filter(code__startswith='commands.navigation.').delete()
    Menu.objects.filter(key='/commands/navigation').delete()
    Menu.objects.filter(key='/commands/aliyun').update(sort_order=42)
    Menu.objects.filter(key='/commands/point-resources').update(sort_order=43)
    Menu.objects.filter(key='/commands/points').update(sort_order=44)


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0010_point_resources_and_points'),
    ]

    operations = [
        migrations.CreateModel(
            name='NavigationCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='指令名称')),
                ('command_code', models.CharField(max_length=128, unique=True, verbose_name='指令标识')),
                ('trigger_text', models.CharField(max_length=255, verbose_name='触发话术')),
                ('response_text', models.CharField(max_length=255, verbose_name='回复话术')),
                ('sort', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_visible', models.BooleanField(default=True, verbose_name='前端可见')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '导航指令',
                'verbose_name_plural': '导航指令',
                'ordering': ['sort', 'id'],
            },
        ),
        migrations.RunPython(seed_navigation_command_access_data, unseed_navigation_command_access_data),
    ]
