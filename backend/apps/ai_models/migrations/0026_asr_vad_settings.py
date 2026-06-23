from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0025_knowledge_base_models_and_settings_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='asrconfig',
            name='vad_silence_duration_ms',
            field=models.PositiveIntegerField(default=400, verbose_name='VAD断句检测阈值(ms)'),
        ),
        migrations.AddField(
            model_name='asrconfig',
            name='vad_threshold',
            field=models.FloatField(default=0.0, verbose_name='VAD检测阈值'),
        ),
    ]
