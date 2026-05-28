from django.db import migrations, models
import django.db.models.deletion


POINT_PERMISSION_DATA = [
    ('查看点位资源', 'commands.point_resources.view', 'commands_point_resources', '允许查看点位资源列表与详情'),
    ('创建点位资源', 'commands.point_resources.create', 'commands_point_resources', '允许新增点位资源'),
    ('编辑点位资源', 'commands.point_resources.update', 'commands_point_resources', '允许编辑点位资源'),
    ('删除点位资源', 'commands.point_resources.delete', 'commands_point_resources', '允许删除点位资源'),
    ('查看点位管理', 'commands.points.view', 'commands_points', '允许查看点位列表与详情'),
    ('创建点位管理', 'commands.points.create', 'commands_points', '允许新增点位'),
    ('编辑点位管理', 'commands.points.update', 'commands_points', '允许编辑点位'),
    ('删除点位管理', 'commands.points.delete', 'commands_points', '允许删除点位'),
]


def seed_point_access_data(apps, schema_editor):
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

    point_resource_menu, _ = Menu.objects.update_or_create(
        key='/commands/point-resources',
        defaults={
            'name': '点位资源',
            'path': '/commands/point-resources',
            'icon': 'FileImageOutlined',
            'sort_order': 43,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    point_menu, _ = Menu.objects.update_or_create(
        key='/commands/points',
        defaults={
            'name': '点位管理',
            'path': '/commands/points',
            'icon': 'EnvironmentOutlined',
            'sort_order': 44,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    permission_points = []
    for name, code, module, description in POINT_PERMISSION_DATA:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(permission_point)

    readonly_codes = {'commands.point_resources.view', 'commands.points.view'}
    readonly_permission_points = [item for item in permission_points if item.code in readonly_codes]

    for role in Role.objects.all():
        role.menus.add(point_resource_menu, point_menu)
        if role.code == 'admin':
            role.permission_points.add(*permission_points)
        else:
            role.permission_points.add(*readonly_permission_points)


def unseed_point_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='commands.point_resources.').delete()
    PermissionPoint.objects.filter(code__startswith='commands.points.').delete()
    Menu.objects.filter(key__in=['/commands/point-resources', '/commands/points']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0009_aliyun_command_access_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='PointResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=128, verbose_name='标题')),
                ('resource_type', models.CharField(choices=[('text', '文本'), ('video', '视频'), ('image', '图片'), ('command', '指令')], max_length=20, verbose_name='素材类型')),
                ('text_content', models.TextField(blank=True, default='', verbose_name='文本内容')),
                ('file', models.FileField(blank=True, null=True, upload_to='point-resources/%Y/%m/%d', verbose_name='素材文件')),
                ('file_size', models.BigIntegerField(blank=True, null=True, verbose_name='文件大小(字节)')),
                ('command_source', models.CharField(blank=True, choices=[('manual', '手动输入'), ('control_command', '选择现有指令')], default='', max_length=32, verbose_name='指令来源')),
                ('manual_command', models.CharField(blank=True, default='', max_length=255, verbose_name='手动指令')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_visible', models.BooleanField(default=True, verbose_name='前端可见')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('control_command', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='point_resources', to='resources.controlcommand', verbose_name='现有控制指令')),
            ],
            options={
                'verbose_name': '点位资源',
                'verbose_name_plural': '点位资源',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Point',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='点位名称')),
                ('lookup_key', models.SlugField(max_length=128, unique=True, verbose_name='请求参数')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points', to='resources.pointresource', verbose_name='点位资源')),
            ],
            options={
                'verbose_name': '点位管理',
                'verbose_name_plural': '点位管理',
                'ordering': ['lookup_key', 'id'],
            },
        ),
        migrations.RunPython(seed_point_access_data, unseed_point_access_data),
    ]
