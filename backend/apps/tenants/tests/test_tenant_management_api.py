"""PR-4：平台菜单分配 API 测试（超管 → 公司）。"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import AccountApplication, Menu, PermissionPoint
from apps.tenants.models import Membership, Tenant

User = get_user_model()


class TenantManagementApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root', 'r@x.com', 'pw12345678')
        # 一个普通公司管理员（不应能访问平台端点）
        cls.tenant = Tenant.objects.create(name='公司A', code='comp-a')
        cls.admin_user = User.objects.create_user('tadmin', password='pw12345678')
        Membership.objects.create(user=cls.admin_user, tenant=cls.tenant, is_tenant_admin=True)
        # 取迁移 seed 的业务菜单与特殊菜单
        cls.biz_menu = Menu.objects.filter(audience=Menu.AUDIENCE_ALL, is_active=True).first()
        cls.platform_menu = Menu.objects.get(key='/tenants')      # audience=platform
        cls.admin_menu = Menu.objects.get(key='/employees')       # audience=tenant_admin

    def test_catalog_only_lists_assignable_menus(self):
        self.client.force_authenticate(self.superuser)
        resp = self.client.get('/api/v1/menus/catalog/')
        self.assertEqual(resp.status_code, 200)
        paths = {m['path'] for m in resp.data['menus']}
        self.assertNotIn('/tenants', paths)    # 平台专属不可分配
        self.assertNotIn('/employees', paths)  # 公司管理员专属不可分配
        self.assertIn('permissionPoints', resp.data)

    def test_tenant_list_only_shows_approved_application_companies_by_default(self):
        self.client.force_authenticate(self.superuser)
        linked = Tenant.objects.create(name='Linked', code='linked')
        application = AccountApplication.objects.create(
            username='linkedadmin',
            applicant_name='Linked Admin',
            enterprise_name='Linked',
            phone='13000000001',
            password='hash',
            reason='test',
            tenant=linked,
        )
        AccountApplication.objects.filter(pk=application.pk).update(status=AccountApplication.STATUS_APPROVED)
        inactive = Tenant.objects.create(name='Inactive', code='inactive', is_active=False)
        legacy = Tenant.objects.create(name='Legacy', code='legacy', is_legacy=True)

        resp = self.client.get('/api/v1/tenants/')

        self.assertEqual(resp.status_code, 200)
        tenant_ids = {item['id'] for item in resp.data['results']}
        self.assertIn(linked.id, tenant_ids)
        self.assertNotIn(self.tenant.id, tenant_ids)
        self.assertNotIn(inactive.id, tenant_ids)
        self.assertNotIn(legacy.id, tenant_ids)

    def test_tenant_list_can_include_hidden_companies(self):
        self.client.force_authenticate(self.superuser)
        linked = Tenant.objects.create(name='Linked', code='linked')
        application = AccountApplication.objects.create(
            username='linkedadmin',
            applicant_name='Linked Admin',
            enterprise_name='Linked',
            phone='13000000001',
            password='hash',
            reason='test',
            tenant=linked,
        )
        AccountApplication.objects.filter(pk=application.pk).update(status=AccountApplication.STATUS_APPROVED)
        inactive = Tenant.objects.create(name='Inactive', code='inactive', is_active=False)
        legacy = Tenant.objects.create(name='Legacy', code='legacy', is_legacy=True)

        resp = self.client.get('/api/v1/tenants/?include_hidden=true')

        self.assertEqual(resp.status_code, 200)
        tenant_ids = {item['id'] for item in resp.data['results']}
        self.assertIn(linked.id, tenant_ids)
        self.assertIn(self.tenant.id, tenant_ids)
        self.assertIn(inactive.id, tenant_ids)
        self.assertIn(legacy.id, tenant_ids)

    def test_superuser_can_create_and_assign_menus(self):
        self.client.force_authenticate(self.superuser)
        # 建公司
        resp = self.client.post('/api/v1/tenants/', {'name': '新公司'}, format='json')
        self.assertEqual(resp.status_code, 201)
        tid = resp.data['id']
        # 分配一个业务菜单 + 权限点
        perm = PermissionPoint.objects.filter(is_active=True).first()
        resp = self.client.put(
            f'/api/v1/tenants/{tid}/menus/',
            {'menuIds': [self.biz_menu.id], 'permissionPointIds': [perm.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        tenant = Tenant.objects.get(id=tid)
        self.assertEqual(list(tenant.menus.values_list('id', flat=True)), [self.biz_menu.id])
        self.assertEqual(list(tenant.permission_points.values_list('id', flat=True)), [perm.id])

    def test_assigning_platform_or_admin_menu_is_rejected(self):
        self.client.force_authenticate(self.superuser)
        resp = self.client.put(
            f'/api/v1/tenants/{self.tenant.id}/menus/',
            {'menuIds': [self.platform_menu.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)  # 平台专属菜单不可分配给公司

    def test_tenant_admin_cannot_access_platform_endpoints(self):
        self.client.force_authenticate(self.admin_user)
        # 公司管理员没有 tenant.management.view → 403
        self.assertEqual(self.client.get('/api/v1/tenants/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/menus/catalog/').status_code, 403)

    def test_assign_menus_get_returns_current_selection(self):
        self.client.force_authenticate(self.superuser)
        self.tenant.menus.set([self.biz_menu])
        resp = self.client.get(f'/api/v1/tenants/{self.tenant.id}/menus/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['menuIds'], [self.biz_menu.id])
