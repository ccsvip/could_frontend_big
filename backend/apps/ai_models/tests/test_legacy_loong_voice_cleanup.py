import importlib

from django.apps import apps
from django.test import TestCase

from apps.ai_models.models import TTSProvider, TTSVoice


cleanup_migration = importlib.import_module(
    'apps.ai_models.migrations.0048_remove_legacy_loong_tts_voices'
)


class LegacyLoongVoiceCleanupTests(TestCase):
    def test_cleanup_is_exact_and_aliyun_scoped(self):
        aliyun = TTSProvider.objects.get(code='aliyun')
        other_provider = TTSProvider.objects.create(code='other-tts', name='Other TTS')
        legacy_codes = cleanup_migration.LEGACY_ALIYUN_VOICE_CODES
        self.assertEqual(len(legacy_codes), 54)

        TTSVoice.objects.bulk_create([
            TTSVoice(provider=aliyun, display_name=code, voice_code=code)
            for code in legacy_codes
        ])
        TTSVoice.objects.create(
            provider=other_provider,
            display_name='Same code on another provider',
            voice_code=legacy_codes[0],
        )

        cleanup_migration.remove_legacy_loong_voices(apps, None)

        self.assertFalse(
            TTSVoice.objects.filter(provider=aliyun, voice_code__in=legacy_codes).exists()
        )
        self.assertTrue(
            TTSVoice.objects.filter(provider=other_provider, voice_code=legacy_codes[0]).exists()
        )
        self.assertTrue(
            TTSVoice.objects.filter(
                provider=aliyun,
                voice_code__in=('Cherry', 'Dylan', 'Jada', 'Sunny', 'Jennifer', 'Radio Gol'),
            ).count() >= 6
        )

    def test_cleanup_does_not_touch_cosyvoice_voices(self):
        cosyvoice = TTSProvider.objects.filter(code='cosyvoice').first()
        if cosyvoice is None:
            self.skipTest('CosyVoice provider is not available in this database state')

        code = cleanup_migration.LEGACY_ALIYUN_VOICE_CODES[-1]
        voice = TTSVoice.objects.create(
            provider=cosyvoice,
            display_name='CosyVoice same code',
            voice_code=code,
        )

        cleanup_migration.remove_legacy_loong_voices(apps, None)

        self.assertTrue(TTSVoice.objects.filter(pk=voice.pk).exists())
