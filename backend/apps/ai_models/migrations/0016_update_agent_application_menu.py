from django.db import migrations


def update_agent_application_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    ai_parent = Menu.objects.filter(key='/ai-models').first()
    
    Menu.objects.filter(key='/applications').update(
        key='/ai-models/applications',
        path='/ai-models/applications',
        name='智能体',
        sort_order=54,
        parent=ai_parent
    )


def rollback_agent_application_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    
    Menu.objects.filter(key='/ai-models/applications').update(
        key='/applications',
        path='/applications',
        name='应用管理',
        sort_order=20,
        parent=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0015_tts_settings'),
    ]

    operations = [
        migrations.RunPython(update_agent_application_menu, rollback_agent_application_menu),
    ]
