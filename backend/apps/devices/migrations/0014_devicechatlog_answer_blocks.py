from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0013_devicechatlog_conversation'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicechatlog',
            name='answer_blocks',
            field=models.JSONField(blank=True, default=list, verbose_name='回答内容块'),
        ),
    ]
