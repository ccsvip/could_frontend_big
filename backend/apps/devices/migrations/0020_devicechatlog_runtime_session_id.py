from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('devices', '0019_device_tts_voice_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicechatlog',
            name='runtime_session_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='本地运行时会话 ID'),
        ),
    ]
