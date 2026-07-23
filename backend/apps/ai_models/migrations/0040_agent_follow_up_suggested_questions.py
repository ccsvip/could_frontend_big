from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0039_remove_bailianknowledgeconfig_category_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='follow_up_suggested_questions_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用回答后建议问题'),
        ),
    ]
