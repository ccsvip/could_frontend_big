from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0022_agent_tts_filter_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmmodel',
            name='enable_web_search',
            field=models.BooleanField(default=False, verbose_name='是否支持联网搜索'),
        ),
    ]
