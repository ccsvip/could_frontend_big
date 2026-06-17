from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0021_agent_max_tokens_unlimited'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='tts_filter_punctuation',
            field=models.CharField(blank=True, default='。！？!?；;、', max_length=64, verbose_name='TTS 过滤标点'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='tts_filter_emoji',
            field=models.BooleanField(default=True, verbose_name='TTS 过滤表情'),
        ),
    ]
