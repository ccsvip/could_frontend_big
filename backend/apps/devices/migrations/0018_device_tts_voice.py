from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0035_agent_application_tts_filter_exclude_patterns'),
        ('devices', '0017_allow_duplicate_wake_word_text_per_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='tts_voice',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bound_devices',
                to='ai_models.ttsvoice',
                verbose_name='当前音色',
            ),
        ),
    ]
