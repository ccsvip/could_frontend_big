from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0018_drop_stale_chatconversation_max_tokens_unlimited'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE ai_models_agentapplication DROP COLUMN IF EXISTS max_tokens_unlimited;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
