"""PR-5：员工管理 + 租户级角色 + 首登改密 API 测试。"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Menu, PermissionPoint, Role, UserRole
from apps.tenants.models import Membership, Tenant

User = get_user_model()


class EmployeeManagementApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # 公司 A，被分配一个业务菜单 + 权限点
        cls.tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
        cls.menu = Menu.objects.create(name='设备', key='/e-devices', path='/e-devices', audience=Menu.AUDIENCE_ALL, sort_order=10)
        cls.perm = PermissionPoint.objects.create(name='查看设备', code='e.devices.view', module='devices')
        cls.tenant_a.menus.set([cls.menu])
        cls.tenant_a.permission_points.set([cls.perm])
        cls.admin_a = User.objects.create_user('admin_a', password='pw12345678')
        Membership.objects.create(user=cls.admin_a, tenant=cls.tenant_a, is_tenant_admin=True)

        # 公司 B（用于跨租户隔离断言）
        cls.tenant_b = Tenant.objects.create(name='公司B', code='comp-b')
        cls.admin_b = User.objects.create_user('admin_b', password='pw12345678')
        Membership.objects.create(user=cls.admin_b, tenant=cls.tenant_b, is_tenant_admin=True)

    def test_admin_creates_employee_with_must_change_password(self):
        self.client.force_authenticate(self.admin_a)
        resp = self.client.post('/api/v1/employees/', {
            'username': 'empA1', 'displayName': '员工一', 'password': 'init12345678', 'roleName': '运营',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['mustChangePassword'])
        self.assertEqual(resp.data['roleName'], '运营')
        emp = User.objects.get(username='empA1')
        m = Membership.objects.get(user=emp)
        self.assertEqual(m.tenant_id, self.tenant_a.id)
        self.assertFalse(m.is_tenant_admin)
        self.assertTrue(m.must_change_password)
        self.assertEqual(m.role_name, '运营')

    def test_employee_role_name_is_required_but_can_repeat(self):
        self.client.force_authenticate(self.admin_a)
        missing = self.client.post('/api/v1/employees/', {
            'username': 'empNoRole', 'displayName': '无角色名', 'password': 'init12345678',
        }, format='json')
        self.assertEqual(missing.status_code, 400)
        self.assertIn('必填', str(missing.data))

        for username in ['sameRole1', 'sameRole2']:
            resp = self.client.post('/api/v1/employees/', {
                'username': username, 'displayName': username, 'password': 'init12345678', 'roleName': '客服',
            }, format='json')
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(resp.data['roleName'], '客服')

    def test_duplicate_username_friendly_error(self):
        self.client.force_authenticate(self.admin_a)
        User.objects.create_user('takenname', password='x12345678')
        resp = self.client.post('/api/v1/employees/', {
            'username': 'takenname', 'displayName': '冲突', 'password': 'init12345678', 'roleName': '员工',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('已被占用', str(resp.data))

    def test_employee_list_scoped_to_own_company(self):
        # A 建一个员工，B 建一个员工，互相看不到
        self.client.force_authenticate(self.admin_a)
        self.client.post('/api/v1/employees/', {'username': 'aEmp', 'displayName': 'a', 'password': 'init12345678', 'roleName': '员工'}, format='json')
        self.client.force_authenticate(self.admin_b)
        self.client.post('/api/v1/employees/', {'username': 'bEmp', 'displayName': 'b', 'password': 'init12345678', 'roleName': '员工'}, format='json')

        self.client.force_authenticate(self.admin_a)
        resp = self.client.get('/api/v1/employees/')
        usernames = {row['username'] for row in (resp.data['results'] if isinstance(resp.data, dict) else resp.data)}
        self.assertEqual(usernames, {'aEmp'})

    def test_reset_password_sets_must_change(self):
        self.client.force_authenticate(self.admin_a)
        self.client.post('/api/v1/employees/', {'username': 'resetEmp', 'displayName': 'r', 'password': 'init12345678', 'roleName': '员工'}, format='json')
        emp = User.objects.get(username='resetEmp')
        # 先把标志清掉模拟员工已改过密
        Membership.objects.filter(user=emp).update(must_change_password=False)
        resp = self.client.post(f'/api/v1/employees/{emp.id}/reset-password/', {'newPassword': 'newpw12345678'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Membership.objects.get(user=emp).must_change_password)

    def test_admin_updates_employee_profile_fields(self):
        self.client.force_authenticate(self.admin_a)
        self.client.post('/api/v1/employees/', {
            'username': 'editEmp', 'displayName': '旧姓名', 'password': 'init12345678', 'roleName': '旧角色',
        }, format='json')
        emp = User.objects.get(username='editEmp')

        resp = self.client.patch(f'/api/v1/employees/{emp.id}/', {
            'username': 'editedEmp', 'displayName': '新姓名', 'roleName': '新角色',
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['username'], 'editedEmp')
        self.assertEqual(resp.data['displayName'], '新姓名')
        self.assertEqual(resp.data['roleName'], '新角色')
        emp.refresh_from_db()
        self.assertEqual(emp.username, 'editedEmp')
        self.assertEqual(emp.first_name, '新姓名')
        self.assertEqual(Membership.objects.get(user=emp).role_name, '新角色')

    def test_admin_cannot_update_employee_to_duplicate_username(self):
        self.client.force_authenticate(self.admin_a)
        User.objects.create_user('existing', password='x12345678')
        self.client.post('/api/v1/employees/', {
            'username': 'willEdit', 'displayName': '员工', 'password': 'init12345678', 'roleName': '员工',
        }, format='json')
        emp = User.objects.get(username='willEdit')

        resp = self.client.patch(f'/api/v1/employees/{emp.id}/', {'username': 'existing'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('已被占用', str(resp.data))

    def test_admin_deletes_employee(self):
        self.client.force_authenticate(self.admin_a)
        self.client.post('/api/v1/employees/', {
            'username': 'deleteEmp', 'displayName': '待删', 'password': 'init12345678', 'roleName': '员工',
        }, format='json')
        emp = User.objects.get(username='deleteEmp')

        resp = self.client.delete(f'/api/v1/employees/{emp.id}/')

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(User.objects.filter(username='deleteEmp').exists())
        self.assertFalse(Membership.objects.filter(user_id=emp.id).exists())

    def test_role_menu_clamped_to_tenant_grant(self):
        # 公司角色不能引用未被授权的菜单
        self.client.force_authenticate(self.admin_a)
        foreign_menu = Menu.objects.create(name='外部', key='/e-foreign', path='/e-foreign', audience=Menu.AUDIENCE_ALL, sort_order=99)
        resp = self.client.post('/api/v1/roles/', {
            'name': '运营', 'code': 'op', 'menuIds': [foreign_menu.id],
        }, format='json')
        self.assertEqual(resp.status_code, 400)  # 越界菜单被拒
        # 用被授权菜单则成功
        resp = self.client.post('/api/v1/roles/', {
            'name': '运营', 'code': 'op', 'menuIds': [self.menu.id], 'permissionPointIds': [self.perm.id],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        role = Role.objects.get(tenant=self.tenant_a, code='op')
        self.assertEqual(list(role.menus.values_list('id', flat=True)), [self.menu.id])

    def test_role_code_unique_per_tenant_not_global(self):
        # A 和 B 可以各建一个同 code 的角色
        self.client.force_authenticate(self.admin_a)
        self.assertEqual(self.client.post('/api/v1/roles/', {'name': '运营', 'code': 'op'}, format='json').status_code, 201)
        self.client.force_authenticate(self.admin_b)
        self.assertEqual(self.client.post('/api/v1/roles/', {'name': '运营', 'code': 'op'}, format='json').status_code, 201)

    def test_employee_cannot_access_employee_endpoints(self):
        # 普通员工（无 tenant.employees.manage）不能访问员工管理端点
        emp = User.objects.create_user('plain_emp', password='pw12345678')
        Membership.objects.create(user=emp, tenant=self.tenant_a, is_tenant_admin=False)
        self.client.force_authenticate(emp)
        self.assertEqual(self.client.get('/api/v1/employees/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/roles/').status_code, 403)
