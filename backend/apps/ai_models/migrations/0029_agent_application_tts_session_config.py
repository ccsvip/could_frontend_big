from django.db import migrations, models

import apps.ai_models.models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0028_agent_application_publish_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='tts_session_config',
            field=models.JSONField(
                blank=True,
                default=apps.ai_models.models.default_agent_tts_session_config,
                verbose_name='TTS 会话配置',
            ),
        ),
    ]
