from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0004_chatconversation_temperature_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='summary',
            field=models.CharField(blank=True, default='', max_length=256, verbose_name='会话摘要'),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='feedback',
            field=models.CharField(
                choices=[('none', '未反馈'), ('up', '点赞'), ('down', '点踩')],
                default='none',
                max_length=8,
                verbose_name='反馈',
            ),
        ),
    ]
