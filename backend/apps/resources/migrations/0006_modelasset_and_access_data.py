from django.db import migrations, models


def seed_model_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    resource_parent = Menu.objects.filter(key='/resources').first()
    if resource_parent is None:
        resource_parent, _ = Menu.objects.update_or_create(
            key='/resources',
            defaults={
                'name': '资源管理',
                'path': '/resources',
                'icon': 'PictureOutlined',
                'sort_order': 30,
                'is_active': True,
                'parent_id': None,
            },
        )

    model_menu, _ = Menu.objects.update_or_create(
        key='/resources/models',
        defaults={
            'name': '模型管理',
            'path': '/resources/models',
            'icon': 'RobotOutlined',
            'sort_order': 34,
            'is_active': True,
            'parent_id': resource_parent.id,
        },
    )

    permission_points = [
        ('查看模型', 'resources.models.view', 'resources_models', '允许查看模型资源'),
        ('创建模型', 'resources.models.create', 'resources_models', '允许创建模型资源'),
        ('编辑模型', 'resources.models.update', 'resources_models', '允许编辑模型资源'),
        ('删除模型', 'resources.models.delete', 'resources_models', '允许删除模型资源'),
    ]

    created_permission_points = []
    for name, code, module, description in permission_points:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': description,
                'is_active': True,
            },
        )
        created_permission_points.append(permission_point)

    for role in Role.objects.all():
        role.menus.add(model_menu)
        role.permission_points.add(*created_permission_points)


def unseed_model_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='resources.models.').delete()
    Menu.objects.filter(key='/resources/models').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_menu_parent'),
        ('resources', '0005_voicetone_icon_is_visible'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModelAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True, verbose_name='模型名称')),
                ('model_type', models.CharField(choices=[('male', '男'), ('female', '女')], max_length=16, verbose_name='模型类型')),
                ('orientation', models.CharField(choices=[('horizontal', '横屏'), ('vertical', '竖屏')], max_length=16, verbose_name='模型方向')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='models/thumbnails/%Y/%m/%d', verbose_name='模型缩略图')),
                ('model_file', models.FileField(blank=True, null=True, upload_to='models/files/%Y/%m/%d', verbose_name='模型文件')),
                ('model_size', models.BigIntegerField(blank=True, null=True, verbose_name='模型大小(字节)')),
                ('cloud_url', models.URLField(blank=True, default='', verbose_name='云端地址')),
                ('is_visible', models.BooleanField(default=True, verbose_name='前端可见')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '模型',
                'verbose_name_plural': '模型',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.RunPython(seed_model_access_data, unseed_model_access_data),
    ]
