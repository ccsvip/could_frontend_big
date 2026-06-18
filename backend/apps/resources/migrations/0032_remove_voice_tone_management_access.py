from django.db import migrations


def remove_voice_tone_management_access(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')

    Menu.objects.filter(key='/resources/voice-tones').delete()


def restore_voice_tone_management_access(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    Role = apps.get_model('accounts', 'Role')

    resource_parent = Menu.objects.filter(key='/resources').first()
    if resource_parent is None:
        resource_parent, _ = Menu.objects.update_or_create(
            key='/resources',
            defaults={
                'name': '资源管理',
                'path': '/resources',
                'icon': 'PictureOutlined',
                'sort_order': 30,
                'is_active': True,
                'parent_id': None,
            },
        )

    voice_tone_menu, _ = Menu.objects.update_or_create(
        key='/resources/voice-tones',
        defaults={
            'name': '音色管理',
            'path': '/resources/voice-tones',
            'icon': 'CustomerServiceOutlined',
            'sort_order': 33,
            'is_active': True,
            'parent_id': resource_parent.id,
        },
    )

    for role in Role.objects.all():
        role.menus.add(voice_tone_menu)


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0031_minioconfig_allow_video_cloud_url'),
    ]

    operations = [
        migrations.RunPython(remove_voice_tone_management_access, restore_voice_tone_management_access),
    ]
