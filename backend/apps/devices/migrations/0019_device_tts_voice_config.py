from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0018_device_tts_voice'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='tts_voice_config',
            field=models.JSONField(blank=True, default=dict, verbose_name='当前音色配置'),
        ),
    ]
