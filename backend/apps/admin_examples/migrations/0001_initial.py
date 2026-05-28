from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0010_point_resources_and_points'),
    ]

    operations = [
        migrations.CreateModel(
            name='PointApiTest',
            fields=[],
            options={
                'verbose_name': '点位接口测试',
                'verbose_name_plural': '点位接口测试',
                'proxy': True,
                'default_permissions': (),
                'indexes': [],
                'constraints': [],
            },
            bases=('resources.point',),
        ),
    ]
