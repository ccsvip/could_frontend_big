from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0026_asr_vad_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='asrconfig',
            name='filter_filler_words',
            field=models.BooleanField(default=True, verbose_name='过滤语气词'),
        ),
    ]
