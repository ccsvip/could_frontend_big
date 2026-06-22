from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0025_knowledge_base_models_and_settings_menu'),
        ('devices', '0010_deviceapplication_agent_application'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceapplication',
            name='tts_voices',
            field=models.ManyToManyField(
                blank=True,
                related_name='device_applications',
                to='ai_models.ttsvoice',
                verbose_name='TTS 音色',
            ),
        ),
    ]
