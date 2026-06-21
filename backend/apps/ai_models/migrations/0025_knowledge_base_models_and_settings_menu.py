import django.db.models.deletion
from django.db import migrations, models


def seed_knowledge_model_settings_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    Role = apps.get_model('accounts', 'Role')

    settings_parent, _ = Menu.objects.update_or_create(
        key='/settings',
        defaults={
            'name': '设置',
            'path': '/settings',
            'icon': 'SettingOutlined',
            'sort_order': 90,
            'is_active': True,
            'audience': 'platform',
            'parent_id': None,
        },
    )
    menu, _ = Menu.objects.update_or_create(
        key='/settings/knowledge-base',
        defaults={
            'name': '知识库',
            'path': '/settings/knowledge-base',
            'icon': 'FileTextOutlined',
            'sort_order': 94,
            'is_active': True,
            'audience': 'platform',
            'parent_id': settings_parent.id,
        },
    )
    for role in Role.objects.filter(tenant__isnull=True):
        if role.code in {'super_admin', 'platform_admin', 'admin'}:
            role.menus.add(settings_parent, menu)


def unseed_knowledge_model_settings_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    Menu.objects.filter(key='/settings/knowledge-base').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0009_menu_audience'),
        ('ai_models', '0024_embeddingmodel_rerankmodel'),
        ('knowledge_base', '0005_knowledgebase_document_relation_and_menu'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantKnowledgeModelSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('embedding_model', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenant_embedding_settings', to='ai_models.embeddingmodel', verbose_name='嵌入模型')),
                ('rerank_model', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenant_rerank_settings', to='ai_models.rerankmodel', verbose_name='重排序模型')),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='knowledge_model_settings', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '公司知识库模型设置',
                'verbose_name_plural': '公司知识库模型设置',
            },
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='knowledge_bases',
            field=models.ManyToManyField(blank=True, related_name='agent_applications', to='knowledge_base.knowledgebase', verbose_name='绑定知识库'),
        ),
        migrations.RunPython(seed_knowledge_model_settings_menu, unseed_knowledge_model_settings_menu),
    ]
