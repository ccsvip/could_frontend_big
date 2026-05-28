from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0025_taskcommandstep_wait_for_inner_tasks'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcommandstep',
            name='is_show',
            field=models.BooleanField(default=True, verbose_name='是否显示到前端'),
        ),
    ]
