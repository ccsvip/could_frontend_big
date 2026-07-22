from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_models.credential_crypto import decrypt_credential
from apps.ai_models.models import BailianKnowledgeConfig, EmbeddingModel, RerankModel, TenantKnowledgeModelSettings
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class KnowledgeModelSettingsApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='knowledge-platform-admin',
            password='test123456',
            email='knowledge-admin@example.com',
        )
        self.tenant_user = User.objects.create_user(username='knowledge-tenant-user', password='test123456')
        self.setup_tenant(self.tenant_user)

    def test_superuser_can_configure_fixed_knowledge_model_slots_without_returning_raw_keys(self):
        self.client.force_authenticate(self.superuser)

        resp = self.client.patch(
            '/api/v1/settings/knowledge-base/models/',
            {
                'embedding': {
                    'alias': '企业知识库向量',
                    'model': 'text-embedding-v4',
                    'baseUrl': 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
                    'apiKey': 'embedding-secret',
                    'dimensions': 1024,
                    'isActive': True,
                },
                'rerank': {
                    'alias': '企业知识库排序',
                    'model': 'qwen3-vl-rerank',
                    'baseUrl': 'https://example.cn-beijing.maas.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
                    'apiKey': 'rerank-secret',
                    'isActive': True,
                },
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['embedding']['alias'], '企业知识库向量')
        self.assertEqual(resp.data['embedding']['model'], 'text-embedding-v4')
        self.assertEqual(resp.data['embedding']['dimensions'], 1024)
        self.assertTrue(resp.data['embedding']['apiKeyConfigured'])
        self.assertEqual(resp.data['rerank']['alias'], '企业知识库排序')
        self.assertEqual(resp.data['rerank']['model'], 'qwen3-vl-rerank')
        self.assertTrue(resp.data['rerank']['apiKeyConfigured'])
        self.assertNotIn('embedding-secret', str(resp.data))
        self.assertNotIn('rerank-secret', str(resp.data))

        self.assertEqual(EmbeddingModel.load_aliyun().api_key, 'embedding-secret')
        self.assertEqual(RerankModel.load_aliyun().api_key, 'rerank-secret')

    def test_non_superuser_cannot_configure_knowledge_model_slots(self):
        self.client.force_authenticate(self.tenant_user)

        get_resp = self.client.get('/api/v1/settings/knowledge-base/models/')
        patch_resp = self.client.patch(
            '/api/v1/settings/knowledge-base/models/',
            {'embedding': {'alias': 'Tenant Alias'}},
            format='json',
        )

        self.assertEqual(get_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_configures_bailian_secret_without_returning_plaintext(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.patch(
            '/api/v1/settings/knowledge-base/models/',
            {
                'bailian': {
                    'accessKeyId': 'access-key-id',
                    'accessKeySecret': 'access-key-secret',
                    'workspaceId': 'workspace-1',
                    'categoryId': 'default',
                    'endpoint': 'bailian.cn-beijing.aliyuncs.com',
                    'isActive': True,
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['bailian']['accessKeySecretConfigured'])
        self.assertNotIn('access-key-secret', str(response.data))
        config = BailianKnowledgeConfig.load()
        self.assertNotEqual(config.access_key_secret_encrypted, 'access-key-secret')
        self.assertEqual(decrypt_credential(config.access_key_secret_encrypted), 'access-key-secret')

        response = self.client.patch(
            '/api/v1/settings/knowledge-base/models/',
            {
                'bailian': {
                    'accessKeyId': '',
                    'accessKeySecret': '',
                    'workspaceId': 'workspace-1',
                    'categoryId': 'default',
                    'endpoint': 'bailian.cn-beijing.aliyuncs.com',
                    'isActive': True,
                },
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.access_key_id, 'access-key-id')
        self.assertEqual(decrypt_credential(config.access_key_secret_encrypted), 'access-key-secret')

    def test_superuser_can_assign_knowledge_models_to_tenant(self):
        embedding = EmbeddingModel.load_aliyun()
        rerank = RerankModel.load_aliyun()
        embedding.name = '公司可见向量别名'
        embedding.save(update_fields=['name', 'updated_at'])
        rerank.name = '公司可见排序别名'
        rerank.save(update_fields=['name', 'updated_at'])
        self.client.force_authenticate(self.superuser)

        resp = self.client.put(
            f'/api/v1/settings/knowledge-base/tenants/{self.tenant.id}/authorization/',
            {
                'embeddingModelId': embedding.id,
                'rerankModelId': rerank.id,
                'managedRagEnabled': True,
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['tenant']['id'], self.tenant.id)
        self.assertEqual(resp.data['models']['embedding']['alias'], '公司可见向量别名')
        self.assertEqual(resp.data['models']['rerank']['alias'], '公司可见排序别名')
        self.assertTrue(resp.data['models']['embedding']['grantIsActive'])
        self.assertTrue(resp.data['models']['rerank']['grantIsActive'])
        self.assertTrue(resp.data['managedRagEnabled'])

        settings = TenantKnowledgeModelSettings.objects.get(tenant=self.tenant)
        self.assertEqual(settings.embedding_model_id, embedding.id)
        self.assertEqual(settings.rerank_model_id, rerank.id)
        self.assertTrue(settings.managed_rag_enabled)
        self.assertTrue(settings.is_active)

    def test_tenant_assignment_rejects_inactive_models(self):
        embedding = EmbeddingModel.load_aliyun()
        embedding.is_active = False
        embedding.save(update_fields=['is_active', 'updated_at'])
        self.client.force_authenticate(self.superuser)

        resp = self.client.put(
            f'/api/v1/settings/knowledge-base/tenants/{self.tenant.id}/authorization/',
            {'embeddingModelId': embedding.id, 'rerankModelId': None, 'isActive': True},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('嵌入模型不存在或未启用', str(resp.data))
