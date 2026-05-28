import os

from django.conf import settings
from django.test import SimpleTestCase


class CacheSettingsTests(SimpleTestCase):
    def test_default_cache_uses_configured_redis_url(self):
        expected_location = os.getenv('REDIS_CACHE_URL') or os.getenv('REDIS_URL') or 'redis://localhost:6379/0'

        self.assertEqual(
            settings.CACHES['default']['BACKEND'],
            'django.core.cache.backends.redis.RedisCache',
        )
        self.assertEqual(settings.CACHES['default']['LOCATION'], expected_location)
