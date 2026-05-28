from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0017_taskcommandstep_delay_seconds'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='cloud_url',
            field=models.URLField(blank=True, default='', verbose_name='云端URL地址'),
        ),
    ]
