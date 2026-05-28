from django.db import migrations, models
import django.db.models.deletion


PERMISSION_POINTS = [
    ('查看滚动文本', 'resources.scrolling_texts.view', 'resources_scrolling_texts', '允许查看滚动文本'),
    ('创建滚动文本', 'resources.scrolling_texts.create', 'resources_scrolling_texts', '允许创建滚动文本'),
    ('编辑滚动文本', 'resources.scrolling_texts.update', 'resources_scrolling_texts', '允许编辑滚动文本'),
    ('删除滚动文本', 'resources.scrolling_texts.delete', 'resources_scrolling_texts', '允许删除滚动文本'),
]


def seed_scrolling_text_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

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

    scrolling_text_menu, _ = Menu.objects.update_or_create(
        key='/resources/scrolling-texts',
        defaults={
            'name': '滚动文本',
            'path': '/resources/scrolling-texts',
            'icon': 'NotificationOutlined',
            'sort_order': 35,
            'is_active': True,
            'parent_id': resource_parent.id,
        },
    )

    created_permissions = []
    for name, code, module, description in PERMISSION_POINTS:
        permission, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': description,
                'is_active': True,
            },
        )
        created_permissions.append(permission)

    view_permissions = [permission for permission in created_permissions if permission.code.endswith('.view')]
    for role in Role.objects.all():
        role.menus.add(resource_parent, scrolling_text_menu)
        if role.code == 'admin':
            role.permission_points.add(*created_permissions)
        else:
            role.permission_points.add(*view_permissions)


def unseed_scrolling_text_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='resources.scrolling_texts.').delete()
    Menu.objects.filter(key='/resources/scrolling-texts').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0019_resource_cloud_url_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrollingText',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=128, verbose_name='标题')),
                (
                    'i18n_scheme',
                    models.CharField(
                        choices=[('zh_en', '中英')],
                        default='zh_en',
                        max_length=32,
                        verbose_name='国际化方案',
                    ),
                ),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '滚动文本',
                'verbose_name_plural': '滚动文本',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ScrollingTextItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(verbose_name='顺序')),
                ('zh_text', models.TextField(verbose_name='中文文本')),
                ('en_text', models.TextField(verbose_name='英文文本')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'scrolling_text',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='items',
                        to='resources.scrollingtext',
                        verbose_name='滚动文本',
                    ),
                ),
            ],
            options={
                'verbose_name': '滚动文本明细',
                'verbose_name_plural': '滚动文本明细',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='scrollingtextitem',
            constraint=models.UniqueConstraint(
                fields=('scrolling_text', 'order'),
                name='unique_scrolling_text_item_order',
            ),
        ),
        migrations.RunPython(seed_scrolling_text_access_data, unseed_scrolling_text_access_data),
    ]
