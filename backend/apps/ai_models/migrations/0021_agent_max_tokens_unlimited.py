from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0020_agent_annotation'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='max_tokens_unlimited',
            field=models.BooleanField(default=False, verbose_name='不限制最大输出 Tokens'),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='max_tokens_unlimited',
            field=models.BooleanField(default=False, verbose_name='不限制最大输出Tokens'),
        ),
    ]
