from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin_examples', '0002_alter_pointapitest_options'),
        ('resources', '0010_point_resources_and_points'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiTester',
            fields=[],
            options={
                'verbose_name': '全部接口测试',
                'verbose_name_plural': '全部接口测试',
                'proxy': True,
                'default_permissions': (),
                'indexes': [],
                'constraints': [],
            },
            bases=('resources.point',),
        ),
    ]
