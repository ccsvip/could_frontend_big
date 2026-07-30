# Generated for 07-29-cosyvoice-tenant-allocation: seed explicit Aliyun/Qwen card
# grants so existing company TTS behaviour keeps working after authorization is
# enforced. CosyVoice and future cards must be granted explicitly by a superuser.
from django.db import migrations


ALIYUN_PROVIDER_CODE = 'aliyun'


def seed_aliyun_grants(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    TTSProvider = apps.get_model('ai_models', 'TTSProvider')
    TenantTTSSettings = apps.get_model('ai_models', 'TenantTTSSettings')
    TenantTTSProviderGrant = apps.get_model('ai_models', 'TenantTTSProviderGrant')

    provider = TTSProvider.objects.filter(code=ALIYUN_PROVIDER_CODE).first()
    if provider is None:
        return

    legacy_configs = {
        row['tenant_id']: row['tts_session_config']
        for row in TenantTTSSettings.objects.values('tenant_id', 'tts_session_config')
    }

    for tenant_id in Tenant.objects.filter(is_active=True).values_list('id', flat=True):
        public_config = legacy_configs.get(tenant_id)
        TenantTTSProviderGrant.objects.update_or_create(
            tenant_id=tenant_id,
            provider_id=provider.id,
            defaults={
                'is_active': True,
                'public_config': dict(public_config) if isinstance(public_config, dict) else {},
            },
        )


def drop_aliyun_grants(apps, schema_editor):
    TTSProvider = apps.get_model('ai_models', 'TTSProvider')
    TenantTTSProviderGrant = apps.get_model('ai_models', 'TenantTTSProviderGrant')

    provider = TTSProvider.objects.filter(code=ALIYUN_PROVIDER_CODE).first()
    if provider is None:
        return
    TenantTTSProviderGrant.objects.filter(provider_id=provider.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0044_tenant_tts_provider_grant'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.RunPython(seed_aliyun_grants, drop_aliyun_grants),
    ]
