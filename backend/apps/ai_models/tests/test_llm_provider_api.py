from rest_framework import status
from rest_framework.test import APITestCase


class DeprecatedLLMProviderApiTests(APITestCase):
    def test_legacy_company_provider_crud_endpoint_is_removed(self):
        response = self.client.get('/api/v1/ai-models/llm-providers/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_legacy_company_provider_test_endpoint_is_removed(self):
        response = self.client.post('/api/v1/ai-models/llm-providers/1/test-connection/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
