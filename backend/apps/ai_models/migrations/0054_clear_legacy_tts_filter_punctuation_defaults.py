from django.db import migrations

LEGACY_DEFAULTS = (
    '。！？!?；;、-',
    '。！？!?；;、',
)


def clear_legacy_defaults(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    for app in AgentApplication.objects.all().iterator():
        update_fields = []
        if app.tts_filter_punctuation in LEGACY_DEFAULTS:
            app.tts_filter_punctuation = ''
            update_fields.append('tts_filter_punctuation')

        published = app.published_config
        if isinstance(published, dict) and published.get('tts_filter_punctuation') in LEGACY_DEFAULTS:
            published = {**published, 'tts_filter_punctuation': ''}
            app.published_config = published
            update_fields.append('published_config')

        if update_fields:
            app.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    # Intentionally irreversible: restoring the legacy default would re-break
    # CosyVoice prosody by stripping sentence punctuation again.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0053_agent_tts_filter_punctuation_default_empty'),
    ]

    operations = [
        migrations.RunPython(clear_legacy_defaults, noop_reverse),
    ]
