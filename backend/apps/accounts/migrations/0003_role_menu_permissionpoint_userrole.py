from django.conf import settings
from django.db import migrations, models


def seed_initial_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    menus = [
        {
            'name': '设备管理',
            'key': '/devices',
            'path': '/devices',
            'icon': 'DesktopOutlined',
            'sort_order': 10,
            'is_active': True,
        },
        {
            'name': '账号申请管理',
            'key': '/account-applications',
            'path': '/account-applications',
            'icon': 'SolutionOutlined',
            'sort_order': 20,
            'is_active': True,
        },
    ]

    for item in menus:
        Menu.objects.update_or_create(
            key=item['key'],
            defaults=item,
        )

    permission_points = [
        {
            'name': '查看设备',
            'code': 'devices.view',
            'module': 'devices',
            'description': '允许查看设备列表和详情',
            'is_active': True,
        },
        {
            'name': '创建设备',
            'code': 'devices.create',
            'module': 'devices',
            'description': '允许新建设备',
            'is_active': True,
        },
        {
            'name': '编辑设备',
            'code': 'devices.update',
            'module': 'devices',
            'description': '允许编辑设备',
            'is_active': True,
        },
        {
            'name': '删除设备',
            'code': 'devices.delete',
            'module': 'devices',
            'description': '允许删除设备',
            'is_active': True,
        },
        {
            'name': '查看账号申请',
            'code': 'account_applications.view',
            'module': 'account_applications',
            'description': '允许查看账号申请管理页面',
            'is_active': True,
        },
        {
            'name': '审核账号申请',
            'code': 'account_applications.review',
            'module': 'account_applications',
            'description': '允许审核账号申请',
            'is_active': True,
        },
    ]

    for item in permission_points:
        PermissionPoint.objects.update_or_create(
            code=item['code'],
            defaults=item,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0002_alter_accountapplication_phone'),
    ]

    operations = [
        migrations.CreateModel(
            name='Menu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='菜单名称')),
                ('key', models.CharField(max_length=128, unique=True, verbose_name='菜单键')),
                ('path', models.CharField(max_length=128, unique=True, verbose_name='路由路径')),
                ('icon', models.CharField(blank=True, default='', max_length=64, verbose_name='图标')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '菜单',
                'verbose_name_plural': '菜单',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='PermissionPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='权限名称')),
                ('code', models.CharField(max_length=128, unique=True, verbose_name='权限编码')),
                ('module', models.CharField(max_length=64, verbose_name='所属模块')),
                ('description', models.TextField(blank=True, default='', verbose_name='权限说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '权限点',
                'verbose_name_plural': '权限点',
                'ordering': ['module', 'code'],
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='角色名称')),
                ('code', models.CharField(max_length=64, unique=True, verbose_name='角色编码')),
                ('description', models.TextField(blank=True, default='', verbose_name='角色说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('menus', models.ManyToManyField(blank=True, related_name='roles', to='accounts.menu', verbose_name='菜单')),
                ('permission_points', models.ManyToManyField(blank=True, related_name='roles', to='accounts.permissionpoint', verbose_name='权限点')),
            ],
            options={
                'verbose_name': '角色',
                'verbose_name_plural': '角色',
                'ordering': ['name', 'id'],
            },
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('role', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='user_bindings', to='accounts.role', verbose_name='角色')),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='role_binding', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户角色绑定',
                'verbose_name_plural': '用户角色绑定',
                'ordering': ['user_id'],
            },
        ),
        migrations.RunPython(seed_initial_access_data, migrations.RunPython.noop),
    ]
