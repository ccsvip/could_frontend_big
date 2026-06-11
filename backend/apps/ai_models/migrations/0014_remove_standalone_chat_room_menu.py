from django.db import migrations


def remove_standalone_chat_room_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    Menu.objects.filter(key='/ai-models/chat').delete()
    Menu.objects.filter(path='/ai-models/chat').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0013_platform_llm_settings'),
    ]

    operations = [
        migrations.RunPython(remove_standalone_chat_room_menu, migrations.RunPython.noop),
    ]
