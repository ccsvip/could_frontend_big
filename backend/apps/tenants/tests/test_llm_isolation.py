"""每公司 LLM 模型授权隔离 + 聊天不跨租户兜底。"""
from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.ai_models.models import ChatConversation
from apps.tenants.models import Membership, Tenant

User = get_user_model()


class LLMTenantIsolationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
        cls.tenant_b = Tenant.objects.create(name='公司B', code='comp-b')

        # is_staff 非 superuser：拿全部权限码（过 CanCreateChat），但 queryset 仍按 membership 租户作用域。
        cls.user_a = User.objects.create_user('ua', password='pw12345678', is_staff=True)
        cls.user_b = User.objects.create_user('ub', password='pw12345678', is_staff=True)
        Membership.objects.create(user=cls.user_a, tenant=cls.tenant_a)
        Membership.objects.create(user=cls.user_b, tenant=cls.tenant_b)

        Provider = apps.get_model('ai_models', 'LLMProvider')
        LLMModel = apps.get_model('ai_models', 'LLMModel')
        CompanyLLMGrant = apps.get_model('ai_models', 'CompanyLLMGrant')
        CompanyLLMSettings = apps.get_model('ai_models', 'CompanyLLMSettings')

        cls.provider_a = Provider.objects.create(
            name='A 的供应商', provider_type='openai',
            api_base_url='https://api.a.com/v1', api_key='secret-a',
            is_active=True,
        )
        cls.model_a = LLMModel.objects.create(
            provider=cls.provider_a,
            display_name='GPT 4.1',
            name='gpt-4.1',
            is_active=True,
        )
        CompanyLLMGrant.objects.create(tenant=cls.tenant_a, model=cls.model_a, is_active=True)
        CompanyLLMSettings.objects.create(tenant=cls.tenant_a, default_model=cls.model_a)

    def test_llm_options_scoped_to_company_grants(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/v1/ai-models/llm/options/')
        names = [p['name'] for p in resp.data['providers']]
        self.assertIn('A 的供应商', names)

        self.client.force_authenticate(self.user_b)
        resp = self.client.get('/api/v1/ai-models/llm/options/')
        names = [p['name'] for p in resp.data['providers']]
        self.assertEqual(names, [])

    def test_chat_send_does_not_fall_back_to_other_tenant_default_model(self):
        conv = ChatConversation.objects.create(title='B 的会话', user=self.user_b, tenant=self.tenant_b)
        self.client.force_authenticate(self.user_b)
        resp = self.client.post(
            f'/api/v1/ai-models/chat/conversations/{conv.id}/send/',
            {'content': '你好', 'stream': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('暂无可用的 LLM 模型', resp.data['message'])
        conv.refresh_from_db()
        self.assertIsNone(conv.llm_model_id)

    def test_cannot_bind_other_tenant_model_via_update_config(self):
        conv = ChatConversation.objects.create(title='B 的会话2', user=self.user_b, tenant=self.tenant_b)
        self.client.force_authenticate(self.user_b)
        resp = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conv.id}/update-config/',
            {'modelId': self.model_a.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        conv.refresh_from_db()
        self.assertIsNone(conv.llm_model_id)
