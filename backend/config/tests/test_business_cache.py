from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.business_cache import (
    clear_business_cache_namespace,
    get_business_cache_summaries,
    get_business_response_cache,
    make_response_cache_key,
    set_business_response_cache,
)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'business-cache-tests',
        }
    }
)
class BusinessCacheTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_response_cache_registers_keys_for_namespace_cleanup(self):
        request = RequestFactory().get('/api/v1/resources/images/?category=horizontal', HTTP_HOST='testserver')
        cache_key = make_response_cache_key('resources', request)

        set_business_response_cache('resources', request, {'count': 1, 'results': [{'name': '背景图'}]})

        self.assertEqual(get_business_response_cache('resources', request)['count'], 1)
        self.assertEqual(get_business_cache_summaries()[0].cache_key_count, 1)

        deleted_count = clear_business_cache_namespace('resources')

        self.assertEqual(deleted_count, 1)
        self.assertIsNone(cache.get(cache_key))
        self.assertIsNone(get_business_response_cache('resources', request))

