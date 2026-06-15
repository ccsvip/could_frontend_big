import json
from pathlib import Path

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEFAULT_TEST_TEXT = '对吧~我就特别喜欢这种超市，尤其是过年的时候去逛超市就会觉得超级超级开心！想买好多好多的东西呢！'
VOICE_ROWS = [
    {'enName': 'Cherry', 'sex': 'female', 'voice': 'Cherry', 'avatar': 'voice_female_one.png', 'visible': True},
    {'enName': 'Serena', 'sex': 'female', 'voice': 'Serena', 'avatar': 'voice_female_two.png', 'visible': True},
    {'enName': 'Ethan', 'sex': 'male', 'voice': 'Ethan', 'avatar': 'voice_male_one.png', 'visible': True},
    {'enName': 'Chelsie', 'sex': 'female', 'voice': 'Chelsie', 'avatar': 'voice_female_three.png', 'visible': True},
    {'enName': 'Dylan（北京话）', 'sex': 'male', 'voice': 'Dylan', 'avatar': 'voice_male_two.png', 'visible': True},
    {'enName': 'Jada（上海话）', 'sex': 'female', 'voice': 'Jada', 'avatar': 'voice_female_four.png', 'visible': True},
    {'enName': 'Sunny（四川话）', 'sex': 'female', 'voice': 'Sunny', 'avatar': 'voice_female_five.png', 'visible': True},
    {'enName': 'Nofish', 'sex': 'male', 'voice': 'Nofish', 'avatar': 'voice_male_three.png', 'visible': True},
    {'enName': 'Jennifer', 'sex': 'female', 'voice': 'Jennifer', 'avatar': 'voice_female_six.png', 'visible': True},
    {'enName': 'Li（南京话）', 'sex': 'male', 'voice': 'Li', 'avatar': 'voice_male_four.png', 'visible': True},
    {'enName': 'Marcus（陕西话）', 'sex': 'male', 'voice': 'Marcus', 'avatar': 'voice_male_five.png', 'visible': True},
    {'enName': 'Roy（闽南语）', 'sex': 'male', 'voice': 'Roy', 'avatar': 'voice_male_six.png', 'visible': True},
    {'enName': 'Peter（天津话）', 'sex': 'male', 'voice': 'Peter', 'avatar': 'voice_male_one.png', 'visible': True},
    {'enName': 'Eric（四川话）', 'sex': 'male', 'voice': 'Eric', 'avatar': 'voice_male_two.png', 'visible': True},
    {'enName': 'Rocky（粤语）', 'sex': 'male', 'voice': 'Rocky', 'avatar': 'voice_male_three.png', 'visible': True},
    {'enName': 'Kiki（粤语）', 'sex': 'female', 'voice': 'Kiki', 'avatar': 'voice_female_seven.png', 'visible': True},
    {'enName': 'Ryan', 'sex': 'male', 'voice': 'Ryan', 'avatar': 'voice_male_four.png', 'visible': True},
    {'enName': 'Katerina', 'sex': 'female', 'voice': 'Katerina', 'avatar': 'voice_female_eight.png', 'visible': True},
    {'enName': 'Elias', 'sex': 'female', 'voice': 'Elias', 'avatar': 'voice_female_five.png', 'visible': True},
    {'enName': 'Momo', 'sex': 'female', 'voice': 'Momo', 'avatar': 'voice_female_one.png', 'visible': True},
    {'enName': 'Moon', 'sex': 'male', 'voice': 'Moon', 'avatar': 'voice_male_two.png', 'visible': True},
    {'enName': 'Maia', 'sex': 'female', 'voice': 'Maia', 'avatar': 'voice_female_three.png', 'visible': True},
    {'enName': 'Kai', 'sex': 'male', 'voice': 'Kai', 'avatar': 'voice_male_six.png', 'visible': True},
    {'enName': 'Bella', 'sex': 'female', 'voice': 'Bella', 'avatar': 'voice_female_four.png', 'visible': True},
    {'enName': 'Aiden', 'sex': 'male', 'voice': 'Aiden', 'avatar': 'voice_male_one.png', 'visible': True},
    {'enName': 'Mia', 'sex': 'female', 'voice': 'Mia', 'avatar': 'voice_female_five.png', 'visible': True},
    {'enName': 'Mochi', 'sex': 'female', 'voice': 'Mochi', 'avatar': 'voice_female_six.png', 'visible': True},
    {'enName': 'Bellona', 'sex': 'female', 'voice': 'Bellona', 'avatar': 'voice_female_seven.png', 'visible': True},
    {'enName': 'Vincent', 'sex': 'male', 'voice': 'Vincent', 'avatar': 'voice_male_three.png', 'visible': True},
    {'enName': 'Bunny', 'sex': 'female', 'voice': 'Bunny', 'avatar': 'voice_female_eight.png', 'visible': True},
    {'enName': 'Neil', 'sex': 'male', 'voice': 'Neil', 'avatar': 'voice_male_four.png', 'visible': True},
    {'enName': 'Arthur', 'sex': 'male', 'voice': 'Arthur', 'avatar': 'voice_male_five.png', 'visible': True},
    {'enName': 'Nini', 'sex': 'female', 'voice': 'Nini', 'avatar': 'voice_female_one.png', 'visible': True},
    {'enName': 'Ebona', 'sex': 'female', 'voice': 'Ebona', 'avatar': 'voice_female_two.png', 'visible': True},
    {'enName': 'Seren', 'sex': 'female', 'voice': 'Seren', 'avatar': 'voice_female_three.png', 'visible': True},
    {'enName': 'Pip', 'sex': 'male', 'voice': 'Pip', 'avatar': 'voice_male_six.png', 'visible': True},
    {'enName': 'Stella', 'sex': 'female', 'voice': 'Stella', 'avatar': 'voice_female_four.png', 'visible': True},
    {'enName': 'Bodega', 'sex': 'male', 'voice': 'Bodega', 'avatar': 'voice_male_one.png', 'visible': True},
    {'enName': 'Sonrisa', 'sex': 'female', 'voice': 'Sonrisa', 'avatar': 'voice_female_five.png', 'visible': True},
    {'enName': 'Alek', 'sex': 'male', 'voice': 'Alek', 'avatar': 'voice_male_two.png', 'visible': True},
    {'enName': 'Dolce', 'sex': 'male', 'voice': 'Dolce', 'avatar': 'voice_male_six.png', 'visible': True},
    {'enName': 'Sohee', 'sex': 'female', 'voice': 'Sohee', 'avatar': 'voice_female_seven.png', 'visible': True},
    {'enName': 'Ono Anna', 'sex': 'female', 'voice': 'Ono Anna', 'avatar': 'voice_female_eight.png', 'visible': True},
    {'enName': 'Lenn', 'sex': 'male', 'voice': 'Lenn', 'avatar': 'voice_male_three.png', 'visible': True},
    {'enName': 'Emilien', 'sex': 'male', 'voice': 'Emilien', 'avatar': 'voice_male_four.png', 'visible': True},
    {'enName': 'Andre', 'sex': 'male', 'voice': 'Andre', 'avatar': 'voice_male_five.png', 'visible': True},
    {'enName': 'Radio Gol', 'sex': 'male', 'voice': 'Radio Gol', 'avatar': 'voice_male_six.png', 'visible': True},
    {'enName': 'Vivian', 'sex': 'female', 'voice': 'Vivian', 'avatar': 'voice_female_one.png', 'visible': True},
]


def load_voice_rows():
    current = Path(__file__).resolve()
    candidates = [
        current.parents[4] / 'wiki' / 'voices_qwen3.json',
        current.parents[4] / 'wiki' / 'voices' / 'voices_qwen3.json',
        current.parents[3] / 'fixtures' / 'tts_voices_qwen3.json',
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get('data') if isinstance(payload, dict) else None
        if isinstance(rows, list) and rows:
            return rows
    return VOICE_ROWS


def seed_tts_data(apps, schema_editor):
    TTSProvider = apps.get_model('ai_models', 'TTSProvider')
    TTSVoice = apps.get_model('ai_models', 'TTSVoice')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    provider, _ = TTSProvider.objects.update_or_create(
        code='aliyun',
        defaults={
            'name': '阿里云 TTS',
            'api_key': getattr(settings, 'ALIYUN_TTS_API_KEY', ''),
            'base_url': getattr(settings, 'ALIYUN_TTS_BASE_URL', ''),
            'model': getattr(settings, 'ALIYUN_TTS_MODEL', 'qwen3-tts-flash-realtime'),
            'sample_rate': getattr(settings, 'ALIYUN_TTS_SAMPLE_RATE', 24000),
            'default_test_text': getattr(settings, 'ALIYUN_TTS_DEFAULT_TEST_TEXT', DEFAULT_TEST_TEXT) or DEFAULT_TEST_TEXT,
            'is_active': True,
        },
    )

    default_voice_code = getattr(settings, 'ALIYUN_TTS_DEFAULT_VOICE', 'Cherry') or 'Cherry'
    default_voice = None
    for index, item in enumerate(load_voice_rows()):
        voice_code = str(item.get('voice') or item.get('enName') or '').strip()
        if not voice_code:
            continue
        avatar = str(item.get('avatar') or '').strip()
        voice, _ = TTSVoice.objects.update_or_create(
            provider=provider,
            voice_code=voice_code,
            defaults={
                'display_name': str(item.get('enName') or voice_code).strip(),
                'gender': str(item.get('sex') or '').strip(),
                'avatar_path': f'/static/tts/voices/{avatar}' if avatar else '',
                'is_active': True,
                'is_visible': bool(item.get('visible', True)),
                'sort_order': index,
            },
        )
        if voice_code == default_voice_code:
            default_voice = voice

    if default_voice is None:
        default_voice = TTSVoice.objects.filter(provider=provider, voice_code='Cherry').first()
    if default_voice is not None:
        provider.default_voice = default_voice
        provider.save(update_fields=['default_voice'])

    permission_defs = [
        {
            'name': '查看TTS配置',
            'code': 'ai_models.tts.view',
            'module': 'ai_models_tts',
            'description': '允许查看TTS配置',
            'is_active': True,
        },
        {
            'name': '编辑TTS配置',
            'code': 'ai_models.tts.update',
            'module': 'ai_models_tts',
            'description': '允许选择公司默认TTS音色',
            'is_active': True,
        },
    ]
    permissions = []
    for item in permission_defs:
        permission, _ = PermissionPoint.objects.update_or_create(code=item['code'], defaults=item)
        permissions.append(permission)

    for tenant in Tenant.objects.all():
        tenant.permission_points.add(*permissions)
    for role in Role.objects.filter(code='admin'):
        role.permission_points.add(*permissions)


def unseed_tts_data(apps, schema_editor):
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    PermissionPoint.objects.filter(code__in=['ai_models.tts.view', 'ai_models.tts.update']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0014_remove_standalone_chat_room_menu'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='TTSProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(default='aliyun', max_length=32, unique=True, verbose_name='供应商编码')),
                ('name', models.CharField(default='阿里云 TTS', max_length=128, verbose_name='供应商名称')),
                ('api_key', models.CharField(blank=True, default='', max_length=512, verbose_name='API Key')),
                ('base_url', models.CharField(blank=True, default='', max_length=512, verbose_name='WebSocket URL')),
                ('model', models.CharField(blank=True, default='', max_length=128, verbose_name='模型名称')),
                ('sample_rate', models.PositiveIntegerField(default=24000, verbose_name='采样率')),
                ('default_test_text', models.TextField(default=DEFAULT_TEST_TEXT, verbose_name='默认测试文本')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'TTS 供应商',
                'verbose_name_plural': 'TTS 供应商',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='TTSVoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(max_length=128, verbose_name='展示名称')),
                ('voice_code', models.CharField(max_length=128, verbose_name='音色编码')),
                ('gender', models.CharField(blank=True, default='', max_length=16, verbose_name='性别')),
                ('avatar_path', models.CharField(blank=True, default='', max_length=255, verbose_name='头像路径')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_visible', models.BooleanField(default=True, verbose_name='是否展示')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='voices', to='ai_models.ttsprovider', verbose_name='所属供应商')),
            ],
            options={
                'verbose_name': 'TTS 音色',
                'verbose_name_plural': 'TTS 音色',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TenantTTSSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('default_voice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenant_default_settings', to='ai_models.ttsvoice', verbose_name='默认音色')),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tts_settings', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '公司 TTS 设置',
                'verbose_name_plural': '公司 TTS 设置',
            },
        ),
        migrations.AddField(
            model_name='ttsprovider',
            name='default_voice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='ai_models.ttsvoice', verbose_name='默认音色'),
        ),
        migrations.AddConstraint(
            model_name='ttsvoice',
            constraint=models.UniqueConstraint(fields=('provider', 'voice_code'), name='uniq_tts_voice_provider_code'),
        ),
        migrations.RunPython(seed_tts_data, unseed_tts_data),
    ]
