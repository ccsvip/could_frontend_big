from django.db import migrations, models


def rename_image_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Menu.objects.filter(key='/resources/images').update(name='图片管理')
    permission_labels = {
        'resources.images.view': ('查看图片', '允许查看图片资源'),
        'resources.images.create': ('创建图片', '允许创建图片资源'),
        'resources.images.update': ('编辑图片', '允许编辑图片资源'),
        'resources.images.delete': ('删除图片', '允许删除图片资源'),
    }
    for code, (name, description) in permission_labels.items():
        PermissionPoint.objects.filter(code=code).update(name=name, description=description)


def restore_image_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Menu.objects.filter(key='/resources/images').update(name='背景图片管理')
    permission_labels = {
        'resources.images.view': ('查看背景图片', '允许查看背景图片资源'),
        'resources.images.create': ('创建背景图片', '允许创建背景图片资源'),
        'resources.images.update': ('编辑背景图片', '允许编辑背景图片资源'),
        'resources.images.delete': ('删除背景图片', '允许删除背景图片资源'),
    }
    for code, (name, description) in permission_labels.items():
        PermissionPoint.objects.filter(code=code).update(name=name, description=description)


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0032_remove_voice_tone_management_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='is_digital_human_background',
            field=models.BooleanField(default=False, verbose_name='是否作为数字人背景图'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='resource_type',
            field=models.CharField(
                choices=[('image', '图片'), ('video', '视频')],
                max_length=20,
                verbose_name='资源类型',
            ),
        ),
        migrations.RunPython(rename_image_menu, restore_image_menu),
    ]
