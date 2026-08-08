from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0057_chatmessage_annotation_match'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantTTSVoiceTestText',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('test_text', models.TextField(max_length=2000, verbose_name='试听文本')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tts_voice_test_texts', to='tenants.tenant', verbose_name='所属公司')),
                ('voice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenant_test_texts', to='ai_models.ttsvoice', verbose_name='TTS 音色')),
            ],
            options={
                'verbose_name': '公司 TTS 音色试听文本',
                'verbose_name_plural': '公司 TTS 音色试听文本',
                'constraints': [models.UniqueConstraint(fields=('tenant', 'voice'), name='uniq_tenant_tts_voice_test_text')],
            },
        ),
    ]
