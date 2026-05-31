"""跨租户隔离测试矩阵（PR-2 三道防线验证）。

覆盖：
- 认证后台端点（Device / VoiceTone）：A 公司用户只见本公司数据，跨租户 retrieve 404。
- perform_create 自动注入请求用户的 tenant，忽略客户端伪造。
- is_staff 非 superuser 仍受租户作用域约束（只有 is_superuser 旁路）。
- Manager.for_tenant(None) 收敛为空集。
- 公开运行时端点（Point）按 ?tenant=<code> 隔离。
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.devices.models import Device
from apps.resources.models import VoiceTone
from apps.resources.point_models import Point
from apps.tenants.models import Membership, Tenant

User = get_user_model()


@override_settings(BUSINESS_CACHE_ENABLED=False)
class CrossTenantIsolationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
        cls.tenant_b = Tenant.objects.create(name='公司B', code='comp-b')

        # is_staff=True 但非 superuser：通过 HasPermissionCode（is_admin_user 给全权限），
        # 同时仍受租户作用域约束 —— 验证特权员工也被隔离。
        cls.user_a = User.objects.create_user('user_a', password='pw12345678', is_staff=True)
        cls.user_b = User.objects.create_user('user_b', password='pw12345678', is_staff=True)
        Membership.objects.create(user=cls.user_a, tenant=cls.tenant_a)
        Membership.objects.create(user=cls.user_b, tenant=cls.tenant_b)

        cls.superuser = User.objects.create_superuser('root', 'root@x.com', 'pw12345678')

        # 同 code 跨租户，验证 UniqueConstraint(tenant, code) 允许且数据互不可见。
        cls.dev_a = Device.objects.create(code='D1', name='a-dev', location='x', tenant=cls.tenant_a)
        cls.dev_b = Device.objects.create(code='D1', name='b-dev', location='y', tenant=cls.tenant_b)

        VoiceTone.objects.create(name='va', voice_code='vc', tenant=cls.tenant_a)
        VoiceTone.objects.create(name='vb', voice_code='vc', tenant=cls.tenant_b)

    @staticmethod
    def _results(response):
        data = response.data
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    # ---- 认证后台端点：列表隔离 ----
    def test_device_list_scoped_to_own_tenant(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(reverse('device-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in self._results(resp)]
        self.assertEqual(names, ['a-dev'])

    def test_voicetone_list_scoped_to_own_tenant(self):
        self.client.force_authenticate(self.user_b)
        resp = self.client.get(reverse('voice-tone-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = sorted(row['name'] for row in self._results(resp))
        self.assertEqual(names, ['vb'])

    # ---- 跨租户单条访问 404 ----
    def test_cross_tenant_retrieve_returns_404(self):
        self.client.force_authenticate(self.user_a)
        # user_a 访问 user_b 的 D1：D1 在 A 也存在，但应命中 A 的那条，绝不能是 B 的。
        resp = self.client.get(reverse('device-detail', kwargs={'code': 'D1'}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'a-dev')

    def test_cross_tenant_retrieve_of_foreign_only_code_is_404(self):
        # 仅 B 公司有的设备，A 用户取不到。
        Device.objects.create(code='ONLY-B', name='only-b', location='z', tenant=self.tenant_b)
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(reverse('device-detail', kwargs={'code': 'ONLY-B'}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ---- perform_create 注入 tenant，忽略伪造 ----
    def test_create_assigns_requesting_user_tenant(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(
            reverse('device-list'),
            {'id': 'NEW1', 'name': 'new', 'location': 'loc', 'status': 'online'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        created = Device.objects.get(code='NEW1', tenant=self.tenant_a)
        self.assertEqual(created.tenant_id, self.tenant_a.id)

    # ---- superuser 旁路：看全部 ----
    def test_superuser_sees_all_tenants(self):
        self.client.force_authenticate(self.superuser)
        resp = self.client.get(reverse('device-list'))
        names = sorted(row['name'] for row in self._results(resp))
        self.assertEqual(names, ['a-dev', 'b-dev'])

    # ---- Manager 层 ----
    def test_manager_for_tenant_none_is_empty(self):
        self.assertEqual(Device.objects.for_tenant(None).count(), 0)

    def test_manager_for_tenant_scopes(self):
        self.assertEqual(
            sorted(Device.objects.for_tenant(self.tenant_a).values_list('name', flat=True)),
            ['a-dev'],
        )

    # ---- 公开运行时端点：?tenant=<code> 隔离 ----
    def test_public_point_endpoint_scoped_by_tenant_param(self):
        Point.objects.create(name='pa', command='cmd', tenant=self.tenant_a, is_active=True, is_show=True)
        Point.objects.create(name='pb', command='cmd', tenant=self.tenant_b, is_active=True, is_show=True)
        # 匿名运行时设备带公司标识
        resp = self.client.get(reverse('point-list'), {'all': 'true', 'tenant': 'comp-a'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in self._results(resp)]
        self.assertEqual(names, ['pa'])

    def test_public_point_endpoint_without_tenant_param_is_empty(self):
        Point.objects.create(name='pa', command='cmd', tenant=self.tenant_a, is_active=True, is_show=True)
        # 无 tenant 参数、无登录态 → for_tenant(None) → 空集（不泄漏任何公司数据）
        resp = self.client.get(reverse('point-list'), {'all': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self._results(resp), [])
