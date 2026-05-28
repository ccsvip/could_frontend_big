from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0026_taskcommandstep_is_show'),
    ]

    operations = [
        migrations.AddField(
            model_name='point',
            name='is_show',
            field=models.BooleanField(default=True, verbose_name='是否显示到前端'),
        ),
    ]
