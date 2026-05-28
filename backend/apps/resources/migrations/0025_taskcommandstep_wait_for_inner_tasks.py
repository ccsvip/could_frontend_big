from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0024_taskcommandstep_inner_tasks'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcommandstep',
            name='wait_for_inner_tasks',
            field=models.BooleanField(default=False, verbose_name='是否等待子子任务完成'),
        ),
    ]
