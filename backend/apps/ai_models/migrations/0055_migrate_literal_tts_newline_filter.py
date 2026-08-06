from django.db import migrations

LEGACY_LITERAL_NEWLINE = r'\n'
VISIBLE_WHITESPACE_FILTERS = ' \r\n'


def migrate_literal_newline_filters(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    for application in AgentApplication.objects.all().iterator():
        update_fields = []
        if application.tts_filter_punctuation == LEGACY_LITERAL_NEWLINE:
            application.tts_filter_punctuation = VISIBLE_WHITESPACE_FILTERS
            update_fields.append('tts_filter_punctuation')

        published = application.published_config
        if (
            isinstance(published, dict)
            and published.get('tts_filter_punctuation') == LEGACY_LITERAL_NEWLINE
        ):
            application.published_config = {
                **published,
                'tts_filter_punctuation': VISIBLE_WHITESPACE_FILTERS,
            }
            update_fields.append('published_config')

        if update_fields:
            application.save(update_fields=update_fields)


def restore_literal_newline_filters(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    for application in AgentApplication.objects.all().iterator():
        update_fields = []
        if application.tts_filter_punctuation == VISIBLE_WHITESPACE_FILTERS:
            application.tts_filter_punctuation = LEGACY_LITERAL_NEWLINE
            update_fields.append('tts_filter_punctuation')

        published = application.published_config
        if (
            isinstance(published, dict)
            and published.get('tts_filter_punctuation') == VISIBLE_WHITESPACE_FILTERS
        ):
            application.published_config = {
                **published,
                'tts_filter_punctuation': LEGACY_LITERAL_NEWLINE,
            }
            update_fields.append('published_config')

        if update_fields:
            application.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0054_clear_legacy_tts_filter_punctuation_defaults'),
    ]

    operations = [
        migrations.RunPython(
            migrate_literal_newline_filters,
            restore_literal_newline_filters,
        ),
    ]
