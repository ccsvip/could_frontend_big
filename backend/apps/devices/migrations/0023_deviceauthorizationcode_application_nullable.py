from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0022_device_chat_log_command_dispatch_diagnostics'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deviceauthorizationcode',
            name='application',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='authorization_codes',
                to='devices.deviceapplication',
                verbose_name='绑定应用',
            ),
        ),
    ]
