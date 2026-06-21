import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_knowledge_base_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    ai_parent = Menu.objects.filter(key='/ai-models').first()
    menu, _ = Menu.objects.update_or_create(
        key='/ai-models/knowledge-base',
        defaults={
            'name': '知识库',
            'path': '/ai-models/knowledge-base',
            'icon': 'FileTextOutlined',
            'sort_order': 55,
            'is_active': True,
            'parent_id': ai_parent.id if ai_parent else None,
        },
    )
    old_menu = Menu.objects.filter(key='/knowledge-base').first()
    if old_menu and old_menu.id != menu.id:
        for role in Role.objects.filter(menus=old_menu):
            role.menus.add(menu)
        for tenant in Tenant.objects.filter(menus=old_menu):
            tenant.menus.add(menu)
        old_menu.delete()

    permission_points = list(PermissionPoint.objects.filter(code__startswith='knowledge_base.'))
    for tenant in Tenant.objects.all():
        tenant.menus.add(menu)
        tenant.permission_points.add(*permission_points)


def rollback_knowledge_base_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    old_menu, _ = Menu.objects.update_or_create(
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
    new_menu = Menu.objects.filter(key='/ai-models/knowledge-base').first()
    if new_menu and new_menu.id != old_menu.id:
        for role in Role.objects.filter(menus=new_menu):
            role.menus.add(old_menu)
        for tenant in Tenant.objects.filter(menus=new_menu):
            tenant.menus.add(old_menu)
        new_menu.delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0004_menu_parent'),
        ('ai_models', '0016_update_agent_application_menu'),
        ('knowledge_base', '0004_knowledgedocumentchunk'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeBase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='知识库名称')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='知识库说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_knowledge_bases', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '知识库',
                'verbose_name_plural': '知识库',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='knowledge_base',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documents', to='knowledge_base.knowledgebase', verbose_name='所属知识库'),
        ),
        migrations.AddConstraint(
            model_name='knowledgebase',
            constraint=models.UniqueConstraint(fields=('tenant', 'name'), name='uniq_knowledge_base_tenant_name'),
        ),
        migrations.RunPython(move_knowledge_base_menu, rollback_knowledge_base_menu),
    ]
