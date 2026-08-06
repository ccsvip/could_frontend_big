from django.db import migrations, models


def backfill_enable_web_search(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    LLMModel = apps.get_model('ai_models', 'LLMModel')
    model_flags = dict(LLMModel.objects.values_list('id', 'enable_web_search'))
    to_enable = []
    for application in AgentApplication.objects.exclude(llm_model_id=None).only('id', 'llm_model_id'):
        if model_flags.get(application.llm_model_id):
            to_enable.append(application.id)
    if to_enable:
        AgentApplication.objects.filter(id__in=to_enable).update(enable_web_search=True)


def reverse_backfill_enable_web_search(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    AgentApplication.objects.filter(enable_web_search=True).update(enable_web_search=False)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0051_ttsvoice_is_visible_label'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='enable_web_search',
            field=models.BooleanField(default=False, verbose_name='是否启用联网搜索'),
        ),
        migrations.RunPython(backfill_enable_web_search, reverse_backfill_enable_web_search),
    ]
