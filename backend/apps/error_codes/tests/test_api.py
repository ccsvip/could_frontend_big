from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.error_codes.catalogue import ERROR_DEFINITIONS


class ErrorCodeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = get_user_model().objects.create_superuser('error-code-admin', password='pw123456')
        self.staff = get_user_model().objects.create_user('error-code-staff', password='pw123456', is_staff=True)

    def test_superuser_can_list_filter_and_retrieve_catalogue(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.get('/api/v1/error-codes/', {'category': '设备运行时', 'keyword': '设备'})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 9)
        record = response.data['results'][0]
        self.assertEqual(
            set(record),
            {'code', 'defaultMessage', 'category', 'description', 'recommendedAction', 'transports', 'legacyStatusCode'},
        )
        self.assertEqual(record['category'], '设备运行时')
        self.assertIn('websocket', record['transports'])
        self.assertTrue(record['code'].isdecimal())
        self.assertEqual(
            {item['code'] for item in response.data['results']},
            {definition.code for definition in ERROR_DEFINITIONS if definition.category == '设备运行时'},
        )
        self.assertEqual(
            set(response.data['categories']),
            {'设备运行时', '实时协议', '语音识别', '语音合成', '大语言模型', '智能体', '内部错误'},
        )

        detail = self.client.get('/api/v1/error-codes/1007/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['code'], '1007')
        self.assertEqual(detail.data['legacyStatusCode'], 44014)
        self.assertEqual(detail.data['defaultMessage'], '设备授权已过期')
        self.assertEqual(self.client.get('/api/v1/error-codes/DEVICE_EXPIRED/').status_code, 404)

    def test_superuser_can_retrieve_every_catalogue_definition(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.get('/api/v1/error-codes/', {'page_size': len(ERROR_DEFINITIONS)})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], len(ERROR_DEFINITIONS))
        self.assertEqual(len(response.data['results']), len(ERROR_DEFINITIONS))
        self.assertEqual(
            {
                record['code']: {
                    field: record[field]
                    for field in ('code', 'category', 'defaultMessage', 'description', 'recommendedAction', 'transports')
                }
                for record in response.data['results']
            },
            {
                definition.code: {
                    'code': definition.code,
                    'category': definition.category,
                    'defaultMessage': definition.default_message,
                    'description': definition.description,
                    'recommendedAction': definition.recommended_action,
                    'transports': list(definition.transports),
                }
                for definition in ERROR_DEFINITIONS
            },
        )
        for definition in ERROR_DEFINITIONS:
            with self.subTest(code=definition.code):
                detail = self.client.get(f'/api/v1/error-codes/{definition.code}/')

                self.assertEqual(detail.status_code, 200, detail.data)
                self.assertEqual(
                    {
                        field: detail.data[field]
                        for field in ('code', 'category', 'defaultMessage', 'description', 'recommendedAction', 'transports')
                    },
                    {
                        'code': definition.code,
                        'category': definition.category,
                        'defaultMessage': definition.default_message,
                        'description': definition.description,
                        'recommendedAction': definition.recommended_action,
                        'transports': list(definition.transports),
                    },
                )

    def test_catalogue_codes_are_unique_decimal_values_in_the_supported_range(self):
        codes = [definition.code for definition in ERROR_DEFINITIONS]

        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.isdecimal() and 1001 <= int(code) <= 2000 for code in codes))

    def test_non_superusers_cannot_access_catalogue(self):
        for user in (self.staff, None):
            self.client.force_authenticate(user=user)
            self.assertIn(self.client.get('/api/v1/error-codes/').status_code, {401, 403})
            self.assertIn(self.client.get('/api/v1/error-codes/1007/').status_code, {401, 403})
