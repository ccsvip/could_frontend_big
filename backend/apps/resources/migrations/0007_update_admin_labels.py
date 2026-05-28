from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0006_modelasset_and_access_data'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modelasset',
            options={
                'ordering': ['-updated_at', '-id'],
                'verbose_name': '模型管理',
                'verbose_name_plural': '模型管理',
            },
        ),
        migrations.AlterModelOptions(
            name='resource',
            options={
                'ordering': ['-updated_at', '-id'],
                'verbose_name': '资源（图片/视频）',
                'verbose_name_plural': '资源（图片/视频）',
            },
        ),
    ]
