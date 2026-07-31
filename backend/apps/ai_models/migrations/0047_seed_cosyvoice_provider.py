# Generated for 07-31-cosyvoice-card-auth-test-failures: seed the CosyVoice TTS
# card row. 0043 created CosyVoiceSettings (a OneToOne on TTSProvider) but never
# the provider row it points at, so on any fresh database the card is missing from
# grantable_tts_providers() and a superuser can never allocate CosyVoice to a
# company. Runtime credentials stay in CosyVoiceSettings; this only adds the card.
from django.db import migrations


COSYVOICE_PROVIDER_CODE = 'cosyvoice'
COSYVOICE_PROVIDER_NAME = 'CosyVoice'
# Mirrors apps.ai_models.services.cosyvoice.COSYVOICE_MODEL, inlined because a
# migration must not import business modules. Every other column is left to the
# model default (empty api_key/base_url, sample_rate 24000, default session
# config, is_active True), which matches the hand-made production row.
COSYVOICE_MODEL = 'cosyvoice-v3.5-plus'


def seed_cosyvoice_provider(apps, schema_editor):
    TTSProvider = apps.get_model('ai_models', 'TTSProvider')

    # get_or_create, not update_or_create: the production row (id=4) was configured
    # by hand. This migration fills a missing card and never overwrites one.
    TTSProvider.objects.get_or_create(
        code=COSYVOICE_PROVIDER_CODE,
        defaults={
            'name': COSYVOICE_PROVIDER_NAME,
            'model': COSYVOICE_MODEL,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0046_llmprovider_api_protocol'),
    ]

    operations = [
        # Reverse is a noop on purpose: a data migration cannot distinguish the row
        # it created from the pre-existing production card, and deleting that card
        # would cascade into TenantTTSProviderGrant, silently revoking every company
        # already allocated CosyVoice. Rolling back leaves the card in place.
        migrations.RunPython(seed_cosyvoice_provider, migrations.RunPython.noop),
    ]
