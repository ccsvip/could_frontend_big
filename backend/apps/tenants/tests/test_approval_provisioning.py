"""PR-3：审批通过自动建公司 + 登录返回租户 的行为测试。"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework.test import APITestCase

from apps.accounts.models import AccountApplication
from apps.accounts.serializers import UserSerializer
from apps.tenants.models import Membership, Tenant

User = get_user_model()


class ApprovalProvisionsCompanyTests(APITestCase):
    def _make_application(self, **overrides):
        data = dict(
            username='acme_admin',
            applicant_name='张三',
            enterprise_name='Acme 科技',
            phone='13800000001',
            password=make_password('init12345678'),
            reason='测试',
            status=AccountApplication.STATUS_PENDING,
        )
        data.update(overrides)
        return AccountApplication.objects.create(**data)

    def test_approval_creates_tenant_and_admin_membership(self):
        app = self._make_application()
        self.assertIsNone(app.tenant)

        app.status = AccountApplication.STATUS_APPROVED
        app.save()

        user = User.objects.get(username='acme_admin')
        # 公司被建出来，名字取企业名称
        tenant = Tenant.objects.get(name='Acme 科技')
        # 申请人成为公司管理员
        membership = Membership.objects.get(user=user)
        self.assertEqual(membership.tenant_id, tenant.id)
        self.assertTrue(membership.is_tenant_admin)
        # 回写到申请记录
        app.refresh_from_db()
        self.assertEqual(app.tenant_id, tenant.id)

    def test_tenant_code_is_slug_and_unique_for_chinese_names(self):
        # 两个中文企业名 slugify 都为空，应回退到 company / company-2，且不冲突
        app1 = self._make_application(username='c1', phone='13800000011', enterprise_name='北京公司')
        app2 = self._make_application(username='c2', phone='13800000012', enterprise_name='上海公司')
        app1.status = AccountApplication.STATUS_APPROVED; app1.save()
        app2.status = AccountApplication.STATUS_APPROVED; app2.save()
        codes = set(Tenant.objects.filter(name__in=['北京公司', '上海公司']).values_list('code', flat=True))
        self.assertEqual(len(codes), 2)  # 两个 code 必须不同
        self.assertTrue(all(c for c in codes))  # 都非空

    def test_reapproval_is_idempotent(self):
        app = self._make_application()
        app.status = AccountApplication.STATUS_APPROVED; app.save()
        first_tenant_count = Tenant.objects.count()
        # 再次保存（模拟重复审批）
        app.save()
        self.assertEqual(Tenant.objects.count(), first_tenant_count)
        self.assertEqual(Membership.objects.filter(user__username='acme_admin').count(), 1)

    def test_login_response_includes_tenant(self):
        app = self._make_application()
        app.status = AccountApplication.STATUS_APPROVED; app.save()

        resp = self.client.post('/api/v1/auth/login/', {'username': 'acme_admin', 'password': 'init12345678'}, format='json')
        self.assertEqual(resp.status_code, 200)
        tenant_payload = resp.data['user']['tenant']
        self.assertIsNotNone(tenant_payload)
        self.assertEqual(tenant_payload['name'], 'Acme 科技')
        self.assertTrue(tenant_payload['isTenantAdmin'])
        self.assertIn('must_change_password', resp.data['user'])

    def test_superuser_serializer_has_null_tenant(self):
        su = User.objects.create_superuser('root2', 'root2@x.com', 'pw12345678')
        data = UserSerializer(su).data
        self.assertIsNone(data['tenant'])
        self.assertFalse(data['must_change_password'])
