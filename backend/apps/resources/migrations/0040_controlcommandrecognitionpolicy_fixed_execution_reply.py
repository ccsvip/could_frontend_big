from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0039_controlcommand_backend_send_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlcommandrecognitionpolicy',
            name='fixed_execution_reply',
            field=models.TextField(blank=True, default='', verbose_name='固定执行回复'),
        ),
    ]
