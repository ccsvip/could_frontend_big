"""PR-4：三级 access-context（菜单/权限分级派发）测试。

验证：
- 超管：通用业务菜单 + 平台专属（租户管理），不含公司管理员专属（员工管理）。
- 公司管理员：本公司被分配的业务菜单 + 员工管理；不含租户管理；权限含 tenant.employees.manage。
- 员工：角色菜单 ∩ 公司菜单（永不超出公司授权范围）。
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase

from apps.accounts.models import Menu, PermissionPoint, Role, UserRole
from apps.accounts.services.permissions import build_user_access_context
from apps.tenants.models import Membership, Tenant

User = get_user_model()


def _menu_paths(ctx):
    """扁平化 access-context 菜单树的所有 path。"""
    paths = []

    def walk(items):
        for it in items:
            paths.append(it['path'])
            if it.get('children'):
                walk(it['children'])

    walk(ctx['menus'])
    return set(paths)


class ThreeTierAccessContextTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # 业务菜单（通用，可分配）。用测试专用路径，避免与迁移 seed 的 /devices 等冲突。
        cls.m_devices = Menu.objects.create(name='设备', key='/t-devices', path='/t-devices', audience=Menu.AUDIENCE_ALL, sort_order=10)
        cls.m_resources = Menu.objects.create(name='资源', key='/t-resources', path='/t-resources', audience=Menu.AUDIENCE_ALL, sort_order=20)
        # 特殊菜单（由 PR-4 迁移 seed，这里直接取，避免重复 key 冲突）
        cls.m_tenants = Menu.objects.get(key='/tenants')      # platform
        cls.m_employees = Menu.objects.get(key='/employees')  # tenant_admin

        cls.p_dev_view = PermissionPoint.objects.create(name='查看设备', code='t.devices.view', module='devices')
        cls.p_res_view = PermissionPoint.objects.create(name='查看资源', code='t.resources.view', module='resources')

        # 公司：被分配 设备 + 资源 两个业务菜单 + 对应权限点
        cls.tenant = Tenant.objects.create(name='公司A', code='comp-a')
        cls.tenant.menus.set([cls.m_devices, cls.m_resources])
        cls.tenant.permission_points.set([cls.p_dev_view, cls.p_res_view])

        cls.superuser = User.objects.create_superuser('root', 'r@x.com', 'pw12345678')

        cls.admin_user = User.objects.create_user('tadmin', password='pw12345678')
        Membership.objects.create(user=cls.admin_user, tenant=cls.tenant, is_tenant_admin=True)

        # 员工：角色只给了 设备（资源没给）→ 应只见设备
        cls.employee = User.objects.create_user('emp', password='pw12345678')
        Membership.objects.create(user=cls.employee, tenant=cls.tenant, is_tenant_admin=False)
        cls.emp_role = Role.objects.create(name='运营', code='comp_a_op')
        cls.emp_role.menus.set([cls.m_devices])
        cls.emp_role.permission_points.set([cls.p_dev_view])
        UserRole.objects.create(user=cls.employee, role=cls.emp_role)

    def test_superuser_sees_platform_menu_not_tenant_admin_menu(self):
        ctx = build_user_access_context(self.superuser)
        paths = _menu_paths(ctx)
        self.assertIn('/tenants', paths)       # 平台专属可见
        self.assertIn('/t-devices', paths)     # 业务菜单可见
        self.assertNotIn('/employees', paths)  # 公司管理员专属不可见
        self.assertEqual(ctx['role']['code'], 'admin')

    def test_tenant_admin_sees_assigned_plus_employees_not_tenants(self):
        ctx = build_user_access_context(self.admin_user)
        paths = _menu_paths(ctx)
        self.assertEqual(paths, {'/t-devices', '/t-resources', '/employees'})
        self.assertNotIn('/tenants', paths)
        self.assertEqual(ctx['role']['code'], 'tenant_admin')
        self.assertIn('tenant.employees.manage', ctx['permissions'])
        self.assertIn('t.devices.view', ctx['permissions'])

    def test_employee_sees_role_intersect_tenant_only(self):
        ctx = build_user_access_context(self.employee)
        paths = _menu_paths(ctx)
        # 角色只给设备，所以只见设备；员工管理/租户管理都不可见
        self.assertEqual(paths, {'/t-devices'})
        self.assertNotIn('/employees', paths)
        self.assertNotIn('/t-resources', paths)
        self.assertEqual(ctx['permissions'], ['t.devices.view'])

    def test_employee_cannot_exceed_tenant_grant(self):
        # 给员工角色加一个公司并未被分配的菜单/权限，员工仍不应看到（交集裁剪）
        extra = Menu.objects.create(name='额外', key='/t-extra', path='/t-extra', audience=Menu.AUDIENCE_ALL, sort_order=30)
        extra_perm = PermissionPoint.objects.create(name='额外权限', code='t.extra.view', module='extra')
        self.emp_role.menus.add(extra)
        self.emp_role.permission_points.add(extra_perm)
        ctx = build_user_access_context(self.employee)
        paths = _menu_paths(ctx)
        self.assertNotIn('/t-extra', paths)  # 公司没被分配 → 员工拿不到
        self.assertNotIn('t.extra.view', ctx['permissions'])
