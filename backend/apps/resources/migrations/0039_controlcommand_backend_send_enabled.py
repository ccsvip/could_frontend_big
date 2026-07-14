from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0038_control_command_recognition_policy'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlcommand',
            name='backend_send_enabled',
            field=models.BooleanField(default=False, verbose_name='后端发送'),
        ),
    ]
