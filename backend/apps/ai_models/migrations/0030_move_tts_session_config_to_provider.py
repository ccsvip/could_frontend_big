from django.db import migrations, models

import apps.ai_models.models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0029_agent_application_tts_session_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='ttsprovider',
            name='tts_session_config',
            field=models.JSONField(
                blank=True,
                default=apps.ai_models.models.default_tts_session_config,
                verbose_name='TTS 会话配置',
            ),
        ),
        migrations.AddField(
            model_name='tenantttssettings',
            name='tts_session_config',
            field=models.JSONField(
                blank=True,
                default=apps.ai_models.models.default_tts_session_config,
                verbose_name='TTS 会话配置',
            ),
        ),
        migrations.RemoveField(
            model_name='agentapplication',
            name='tts_session_config',
        ),
    ]
