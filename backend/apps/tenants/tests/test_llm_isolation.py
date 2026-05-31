"""PR-6：每公司 LLM 供应商隔离 + 聊天不跨租户兜底。"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.ai_models.models import ChatConversation, LLMProvider
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

        # 只有公司 A 配了供应商
        cls.provider_a = LLMProvider.objects.create(
            name='A 的供应商', provider_type='openai',
            api_base_url='https://api.a.com/v1', api_key='secret-a',
            models_config=[{'name': 'gpt-4.1', 'isDefault': True}], is_active=True,
            tenant=cls.tenant_a,
        )

    def test_llm_provider_list_scoped_per_tenant(self):
        # A 看得到自己的供应商
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/v1/ai-models/llm-providers/')
        names = [p['name'] for p in (resp.data['results'] if isinstance(resp.data, dict) else resp.data)]
        self.assertIn('A 的供应商', names)
        # B 看不到 A 的供应商
        self.client.force_authenticate(self.user_b)
        resp = self.client.get('/api/v1/ai-models/llm-providers/')
        names = [p['name'] for p in (resp.data['results'] if isinstance(resp.data, dict) else resp.data)]
        self.assertEqual(names, [])

    def test_chat_send_does_not_fall_back_to_other_tenant_provider(self):
        # B 公司没配供应商，发消息时不应兜底到 A 的供应商，而是返回友好错误。
        conv = ChatConversation.objects.create(title='B 的会话', user=self.user_b, tenant=self.tenant_b)
        self.client.force_authenticate(self.user_b)
        resp = self.client.post(
            f'/api/v1/ai-models/chat/conversations/{conv.id}/send/',
            {'content': '你好', 'stream': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('暂无可用的 LLM 供应商', resp.data['message'])
        # 确认没有偷偷绑定到 A 的供应商
        conv.refresh_from_db()
        self.assertIsNone(conv.llm_provider_id)

    def test_cannot_bind_other_tenant_provider_via_update_config(self):
        conv = ChatConversation.objects.create(title='B 的会话2', user=self.user_b, tenant=self.tenant_b)
        self.client.force_authenticate(self.user_b)
        resp = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conv.id}/update-config/',
            {'llmProviderId': self.provider_a.id, 'modelName': 'gpt-4.1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        conv.refresh_from_db()
        # A 的供应商不在 B 范围内 → 绑定被忽略（置空），不会串租户。
        self.assertIsNone(conv.llm_provider_id)
