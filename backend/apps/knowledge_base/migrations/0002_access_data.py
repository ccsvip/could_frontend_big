from django.db import migrations


def seed_knowledge_base_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    menu, _ = Menu.objects.update_or_create(
        key='/knowledge-base',
        defaults={
            'name': '知识库',
            'path': '/knowledge-base',
            'icon': 'FileTextOutlined',
            'sort_order': 35,
            'is_active': True,
            'parent_id': None,
        },
    )

    permission_points = []
    for name, code, description in [
        ('查看知识库', 'knowledge_base.view', '允许查看知识库列表与详情'),
        ('上传知识库文档', 'knowledge_base.upload', '允许上传知识库文档'),
        ('下载知识库文档', 'knowledge_base.download', '允许下载单个知识库文档'),
        ('批量下载知识库文档', 'knowledge_base.bulk_download', '允许批量下载知识库文档'),
    ]:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': 'knowledge_base',
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(permission_point)

    for role in Role.objects.all():
        role.menus.add(menu)
        role.permission_points.add(*permission_points)


def unseed_knowledge_base_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='knowledge_base.').delete()
    Menu.objects.filter(key='/knowledge-base').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_menu_parent'),
        ('knowledge_base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_knowledge_base_access_data, unseed_knowledge_base_access_data),
    ]

