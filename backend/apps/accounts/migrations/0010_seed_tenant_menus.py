from django.db import migrations


def seed_tenant_menus(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    menus = [
        {
            # 平台超管专属：管理所有公司、给公司分配菜单。员工/公司管理员都看不到。
            'name': '租户管理',
            'key': '/tenants',
            'path': '/tenants',
            'icon': 'ApartmentOutlined',
            'audience': 'platform',
            'sort_order': 1,
            'is_active': True,
        },
        {
            # 公司管理员专属：管理本公司员工。员工看不到，也不在可分配目录里。
            'name': '员工管理',
            'key': '/employees',
            'path': '/employees',
            'icon': 'TeamOutlined',
            'audience': 'tenant_admin',
            'sort_order': 2,
            'is_active': True,
        },
    ]
    for item in menus:
        Menu.objects.update_or_create(key=item['key'], defaults=item)

    permission_points = [
        {
            'name': '租户管理',
            'code': 'tenant.management.view',
            'module': 'tenants',
            'description': '允许平台超管管理公司与菜单分配',
            'is_active': True,
        },
        {
            'name': '员工管理',
            'code': 'tenant.employees.manage',
            'module': 'tenants',
            'description': '允许公司管理员管理本公司员工',
            'is_active': True,
        },
    ]
    for item in permission_points:
        PermissionPoint.objects.update_or_create(code=item['code'], defaults=item)


def unseed_tenant_menus(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Menu.objects.filter(key__in=['/tenants', '/employees']).delete()
    PermissionPoint.objects.filter(code__in=['tenant.management.view', 'tenant.employees.manage']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_menu_audience'),
    ]

    operations = [
        migrations.RunPython(seed_tenant_menus, unseed_tenant_menus),
    ]
