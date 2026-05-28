from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0002_chatconversation_chatmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='system_prompt',
            field=models.TextField(blank=True, default='', verbose_name='系统提示词'),
        ),
    ]
