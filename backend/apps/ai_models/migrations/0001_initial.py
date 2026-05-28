from django.db import migrations, models


def seed_ai_models_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    ai_parent, _ = Menu.objects.update_or_create(
        key='/ai-models',
        defaults={
            'name': 'AI大模型',
            'path': '/ai-models',
            'icon': 'CloudOutlined',
            'sort_order': 50,
            'is_active': True,
            'parent_id': None,
        },
    )

    asr_menu, _ = Menu.objects.update_or_create(
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

    llm_menu, _ = Menu.objects.update_or_create(
        key='/ai-models/llm',
        defaults={
            'name': 'LLM管理',
            'path': '/ai-models/llm',
            'icon': 'CloudOutlined',
            'sort_order': 52,
            'is_active': True,
            'parent_id': ai_parent.id,
        },
    )

    tts_menu, _ = Menu.objects.update_or_create(
        key='/ai-models/tts',
        defaults={
            'name': 'TTS管理',
            'path': '/ai-models/tts',
            'icon': 'SoundOutlined',
            'sort_order': 53,
            'is_active': True,
            'parent_id': ai_parent.id,
        },
    )

    permission_defs = [
        ('查看ASR配置', 'ai_models.asr.view', 'ai_models_asr', '允许查看ASR配置'),
        ('查看TTS配置', 'ai_models.tts.view', 'ai_models_tts', '允许查看TTS配置'),
        ('查看LLM供应商', 'ai_models.llm.view', 'ai_models_llm', '允许查看LLM供应商列表'),
        ('创建LLM供应商', 'ai_models.llm.create', 'ai_models_llm', '允许新增LLM供应商'),
        ('编辑LLM供应商', 'ai_models.llm.update', 'ai_models_llm', '允许编辑LLM供应商'),
        ('删除LLM供应商', 'ai_models.llm.delete', 'ai_models_llm', '允许删除LLM供应商'),
    ]

    permission_points = []
    for name, code, module, description in permission_defs:
        pp, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(pp)

    readonly_codes = {'ai_models.asr.view', 'ai_models.tts.view', 'ai_models.llm.view'}
    readonly_pps = [p for p in permission_points if p.code in readonly_codes]

    child_menus = [asr_menu, llm_menu, tts_menu]

    for role in Role.objects.all():
        role.menus.add(*child_menus)
        if role.code == 'admin':
            role.permission_points.add(*permission_points)
        else:
            role.permission_points.add(*readonly_pps)


def unseed_ai_models_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='ai_models.').delete()
    Menu.objects.filter(key__startswith='/ai-models').delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('accounts', '0004_menu_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='LLMProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='供应商名称')),
                ('provider_type', models.CharField(
                    choices=[
                        ('openai', 'OpenAI'), ('gemini', 'Gemini'), ('claude', 'Claude'),
                        ('kimi', 'Kimi'), ('doubao', '豆包'), ('deepseek', 'DeepSeek'),
                        ('qwen', '通义千问'), ('zhipu', '智谱'), ('other', '其他'),
                    ],
                    default='openai', max_length=32, verbose_name='供应商类型',
                )),
                ('api_base_url', models.URLField(max_length=512, verbose_name='API 地址')),
                ('api_key', models.CharField(max_length=512, verbose_name='API 密钥')),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='ai_models/avatars/', verbose_name='供应商头像')),
                ('models_config', models.JSONField(blank=True, default=list, verbose_name='模型列表')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'LLM 供应商',
                'verbose_name_plural': 'LLM 供应商',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(seed_ai_models_access_data, unseed_ai_models_access_data),
    ]
