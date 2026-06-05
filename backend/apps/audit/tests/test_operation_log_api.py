"""审计中间件 + 操作日志只读 API 的最小测试。

覆盖：
- 成功的写请求（POST 创建公司）会自动写入一条 OperationLog；
- GET 请求不写日志；
- 审计日志查询接口为平台超管专属，普通公司管理员 403。
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import OperationLog
from apps.tenants.models import Membership, Tenant

User = get_user_model()


class OperationLogMiddlewareTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root', 'r@x.com', 'pw12345678')

    def setUp(self):
        self.client.force_authenticate(self.superuser)

    def test_successful_write_creates_one_log(self):
        before = OperationLog.objects.count()
        resp = self.client.post('/api/v1/tenants/', {'name': '审计公司'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.assertEqual(OperationLog.objects.count(), before + 1)
        log = OperationLog.objects.order_by('-created_at').first()
        self.assertEqual(log.description, '新增公司：审计公司')
        self.assertEqual(log.action, 'create')
        self.assertEqual(log.method, 'POST')
        self.assertEqual(log.path, '/api/v1/tenants/')
        self.assertEqual(log.status_code, status.HTTP_201_CREATED)
        self.assertEqual(log.actor_id, self.superuser.id)
        self.assertEqual(log.actor_username, 'root')

        audit_resp = self.client.get('/api/v1/audit/logs/')
        self.assertEqual(audit_resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(audit_resp.data['count'], 1)
        self.assertEqual(audit_resp.data['results'][0]['description'], '新增公司：审计公司')

    def test_get_request_is_not_logged(self):
        before = OperationLog.objects.count()
        resp = self.client.get('/api/v1/tenants/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(OperationLog.objects.count(), before)

    def test_failed_write_is_not_logged(self):
        # 缺少必填 name → 400，失败的写操作不留痕。
        before = OperationLog.objects.count()
        resp = self.client.post('/api/v1/tenants/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OperationLog.objects.count(), before)

    def test_audit_logs_endpoint_lists_logs_for_superuser(self):
        self.client.post('/api/v1/tenants/', {'name': '审计公司2'}, format='json')
        resp = self.client.get('/api/v1/audit/logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # 默认分页，结果在 results 中。
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_tenant_admin_lists_only_own_tenant_logs(self):
        tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
        tenant_b = Tenant.objects.create(name='公司B', code='comp-b')
        admin_a = User.objects.create_user('admin-a', password='pw12345678')
        Membership.objects.create(user=admin_a, tenant=tenant_a, is_tenant_admin=True)
        OperationLog.objects.create(
            actor_username='a1',
            tenant=tenant_a,
            action='create',
            method='POST',
            path='/api/v1/resources/images/',
            status_code=201,
            description='新增图片资源 A',
        )
        OperationLog.objects.create(
            actor_username='b1',
            tenant=tenant_b,
            action='delete',
            method='DELETE',
            path='/api/v1/resources/images/1/',
            status_code=204,
            description='删除图片资源 B',
        )

        self.client.force_authenticate(admin_a)
        resp = self.client.get(f'/api/v1/audit/logs/?tenant={tenant_b.id}')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['tenant'], tenant_a.id)

    def test_tenant_admin_clears_only_own_tenant_logs(self):
        tenant_a = Tenant.objects.create(name='公司A', code='clear-a')
        tenant_b = Tenant.objects.create(name='公司B', code='clear-b')
        admin_a = User.objects.create_user('clear-admin-a', password='pw12345678')
        Membership.objects.create(user=admin_a, tenant=tenant_a, is_tenant_admin=True)
        OperationLog.objects.create(
            actor_username='a1',
            tenant=tenant_a,
            action='create',
            method='POST',
            path='/api/v1/resources/images/',
            status_code=201,
            description='新增图片资源 A',
        )
        OperationLog.objects.create(
            actor_username='b1',
            tenant=tenant_b,
            action='delete',
            method='DELETE',
            path='/api/v1/resources/images/1/',
            status_code=204,
            description='删除图片资源 B',
        )

        self.client.force_authenticate(admin_a)
        resp = self.client.delete('/api/v1/audit/logs/clear/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 1)
        self.assertFalse(OperationLog.objects.filter(tenant=tenant_a).exists())
        self.assertTrue(OperationLog.objects.filter(tenant=tenant_b).exists())

    def test_superuser_clears_all_logs(self):
        tenant = Tenant.objects.create(name='公司C', code='clear-c')
        OperationLog.objects.create(
            actor_username='root',
            tenant=None,
            action='create',
            method='POST',
            path='/api/v1/tenants/',
            status_code=201,
            description='新增公司',
        )
        OperationLog.objects.create(
            actor_username='admin',
            tenant=tenant,
            action='create',
            method='POST',
            path='/api/v1/resources/images/',
            status_code=201,
            description='新增图片资源',
        )

        self.client.force_authenticate(self.superuser)
        resp = self.client.delete('/api/v1/audit/logs/clear/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 2)
        self.assertEqual(OperationLog.objects.count(), 0)

    def test_audit_logs_endpoint_forbidden_for_staff_non_superuser(self):
        # 安全边界：is_staff 但非 superuser 且无公司归属，不得读取审计日志。
        staff_user = User.objects.create_user('staffer', password='pw12345678', is_staff=True)

        self.client.force_authenticate(staff_user)
        resp = self.client.get('/api/v1/audit/logs/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
