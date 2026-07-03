from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0034_third_party_chatbot_scheme_b'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='tts_filter_exclude_patterns',
            field=models.JSONField(blank=True, default=list, verbose_name='TTS 排除文本'),
        ),
    ]
