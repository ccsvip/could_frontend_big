from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0016_backend_management_flow_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcommandstep',
            name='delay_seconds',
            field=models.PositiveIntegerField(default=0, verbose_name='延迟时间（秒）'),
        ),
    ]
