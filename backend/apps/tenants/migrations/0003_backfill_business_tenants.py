from django.db import migrations


# (app_label, model_name) —— 所有加了 tenant 外键、需回填默认公司的业务模型。
TENANT_SCOPED_MODELS = [
    ('devices', 'Device'),
    ('resources', 'Resource'),
    ('resources', 'ScrollingText'),
    ('resources', 'CommandGroup'),
    ('resources', 'VoiceTone'),
    ('resources', 'ModelAsset'),
    ('resources', 'ControlCommand'),
    ('resources', 'TaskCommand'),
    ('resources', 'Point'),
    ('knowledge_base', 'KnowledgeDocument'),
    ('ai_models', 'LLMProvider'),
    ('ai_models', 'ChatConversation'),
]


def backfill_default_tenant(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    tenant = Tenant.objects.filter(code='default').first()
    if tenant is None:
        return
    # 把 seed_devices / seed 迁移建出的历史业务行（tenant=NULL）收容进默认公司，
    # 避免成为对所有租户都不可见的孤儿行。
    for app_label, model_name in TENANT_SCOPED_MODELS:
        model = apps.get_model(app_label, model_name)
        model.objects.filter(tenant__isnull=True).update(tenant=tenant)


def clear_default_tenant(apps, schema_editor):
    # 反向：把默认公司的业务行 tenant 置空，恢复加列前状态。
    Tenant = apps.get_model('tenants', 'Tenant')
    tenant = Tenant.objects.filter(code='default').first()
    if tenant is None:
        return
    for app_label, model_name in TENANT_SCOPED_MODELS:
        model = apps.get_model(app_label, model_name)
        model.objects.filter(tenant=tenant).update(tenant=None)


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0002_default_company'),
        ('devices', '0002_device_tenant_alter_device_code_and_more'),
        ('resources', '0028_commandgroup_tenant_controlcommand_tenant_and_more'),
        ('knowledge_base', '0003_knowledgedocument_tenant'),
        ('ai_models', '0006_chatconversation_tenant_llmprovider_tenant'),
    ]

    operations = [
        migrations.RunPython(backfill_default_tenant, clear_default_tenant),
    ]
