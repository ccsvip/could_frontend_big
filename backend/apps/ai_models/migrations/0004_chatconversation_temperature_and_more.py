from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0003_chatconversation_system_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='max_tokens',
            field=models.PositiveIntegerField(default=1000, verbose_name='最大输出Tokens'),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='temperature',
            field=models.FloatField(default=0.7, verbose_name='Temperature'),
        ),
    ]
