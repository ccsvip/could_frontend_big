from django.db import migrations, models


def seed_asr_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    ai_parent, _ = Menu.objects.update_or_create(
        key='/ai-models',
        defaults={
            'name': 'AI大模型',
            'path': '/ai-models',
            'icon': 'RobotOutlined',
            'sort_order': 50,
            'is_active': True,
            'parent_id': None,
        },
    )
    Menu.objects.update_or_create(
        key='/ai-models/asr',
        defaults={
            'name': 'ASR管理',
            'path': '/ai-models/asr',
            'icon': 'AudioOutlined',
            'sort_order': 51,
            'is_active': True,
            'parent_id': ai_parent.id,
        },
    )
    PermissionPoint.objects.update_or_create(
        code='ai_models.asr.view',
        defaults={
            'name': '查看ASR配置',
            'module': 'ai_models_asr',
            'description': '允许查看ASR状态并测试连接',
            'is_active': True,
        },
    )


def unseed_asr_access_data(apps, schema_editor):
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    PermissionPoint.objects.filter(code='ai_models.asr.view').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0006_chatconversation_tenant_llmprovider_tenant'),
    ]

    operations = [
        migrations.CreateModel(
            name='ASRConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workspace_id', models.CharField(blank=True, default='', max_length=128, verbose_name='Workspace ID')),
                ('api_key', models.CharField(blank=True, default='', max_length=512, verbose_name='API Key')),
                ('base_url', models.CharField(blank=True, default='', max_length=512, verbose_name='WebSocket URL')),
                ('model', models.CharField(blank=True, default='', max_length=128, verbose_name='模型名称')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'ASR 配置',
                'verbose_name_plural': 'ASR 配置',
            },
        ),
        migrations.RunPython(seed_asr_access_data, unseed_asr_access_data),
    ]
