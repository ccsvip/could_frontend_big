from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0017_agent_conversation_settings'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE ai_models_chatconversation DROP COLUMN IF EXISTS max_tokens_unlimited;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
