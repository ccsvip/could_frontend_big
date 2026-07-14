from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0021_device_is_software_trial'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicechatlog',
            name='command_dispatch_diagnostics',
            field=models.JSONField(blank=True, default=dict, verbose_name='控制指令分流诊断'),
        ),
    ]
