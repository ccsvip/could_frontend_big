import django.db.models.deletion
from django.db import migrations, models


def default_opening_message(name: str) -> str:
    agent_name = (name or '智能体').strip() or '智能体'
    return f'你好，我是{agent_name}，很高兴见到你，有什么我可以帮你的吗？'


def backfill_agent_conversation_settings(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    delete_permission, _ = PermissionPoint.objects.update_or_create(
        code='agent_applications.delete',
        defaults={
            'name': '删除智能体',
            'module': 'agent_applications',
            'description': '允许删除智能体应用及其关联会话',
            'is_active': True,
        },
    )

    for tenant in Tenant.objects.all():
        tenant.permission_points.add(delete_permission)

    for role in Role.objects.all():
        if role.code == 'admin':
            role.permission_points.add(delete_permission)

    for application in AgentApplication.objects.all():
        update_fields = []
        if not application.opening_message:
            application.opening_message = default_opening_message(application.name)
            update_fields.append('opening_message')
        if application.suggested_questions is None:
            application.suggested_questions = []
            update_fields.append('suggested_questions')
        if update_fields:
            application.save(update_fields=update_fields)


def rollback_agent_conversation_settings(apps, schema_editor):
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    Tenant = apps.get_model('tenants', 'Tenant')

    delete_permission = PermissionPoint.objects.filter(code='agent_applications.delete').first()
    if delete_permission is None:
        return

    for tenant in Tenant.objects.all():
        tenant.permission_points.remove(delete_permission)
    for role in Role.objects.all():
        role.permission_points.remove(delete_permission)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0016_update_agent_application_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='opening_message_enabled',
            field=models.BooleanField(default=True, verbose_name='是否启用开场白'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='opening_message',
            field=models.TextField(blank=True, default='', verbose_name='开场白'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='suggested_questions',
            field=models.JSONField(blank=True, default=list, verbose_name='建议问题'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='voice_input_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用语音输入'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='reply_playback_enabled',
            field=models.BooleanField(default=False, verbose_name='是否自动播报回复'),
        ),
        migrations.AlterField(
            model_name='chatconversation',
            name='application',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversations',
                to='ai_models.agentapplication',
                verbose_name='绑定应用',
            ),
        ),
        migrations.RunPython(backfill_agent_conversation_settings, rollback_agent_conversation_settings),
    ]
