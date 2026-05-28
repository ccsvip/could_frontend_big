from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0018_resource_cloud_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resource',
            name='cloud_url',
            field=models.URLField(blank=True, default='', max_length=2048, verbose_name='云端URL地址'),
        ),
    ]
