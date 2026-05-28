from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from kombu.exceptions import OperationalError
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import AccountApplication, PermissionPoint, Role, UserRole
from .tasks import notify_account_application

User = get_user_model()


class AuthApiCsrfTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='csrf-user', password='test123456')

    def test_login_allows_request_without_csrf_even_when_session_cookie_exists(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username='csrf-user', password='test123456'))

        response = client.post(
            '/api/v1/auth/login/',
            {'username': 'csrf-user', 'password': 'test123456'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_account_application_allows_request_without_csrf_even_when_session_cookie_exists(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username='csrf-user', password='test123456'))

        with patch('apps.accounts.views.notify_account_application.delay') as notify_delay:
            response = client.post(
                '/api/v1/auth/account-applications/',
                {
                    'username': 'applyuser',
                    'applicantName': '测试申请人',
                    'enterpriseName': '测试企业',
                    'phone': '13800138000',
                    'password': 'apply-pass-1',
                    'confirmPassword': 'apply-pass-1',
                    'reason': '需要使用后台功能',
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['username'], 'applyuser')
        self.assertEqual(response.data['data']['enterpriseName'], '测试企业')
        notify_delay.assert_called_once()

    def test_account_application_falls_back_to_sync_notification_when_celery_unavailable(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username='csrf-user', password='test123456'))

        with (
            patch('apps.accounts.views.notify_account_application.delay', side_effect=OperationalError),
            patch('apps.accounts.views.notify_account_application_created') as notify_sync,
        ):
            response = client.post(
                '/api/v1/auth/account-applications/',
                {
                    'username': 'syncuser',
                    'applicantName': '同步通知申请人',
                    'enterpriseName': '同步企业',
                    'phone': '13800138001',
                    'password': 'sync-pass-1',
                    'confirmPassword': 'sync-pass-1',
                    'reason': '需要使用后台功能',
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notify_sync.assert_called_once()

    def test_account_application_rejects_numeric_password(self):
        client = APIClient()
        response = client.post(
            '/api/v1/auth/account-applications/',
            {
                'username': 'numpwd',
                'applicantName': '纯数字密码',
                'enterpriseName': '某企业',
                'phone': '13800138010',
                'password': '123456',
                'confirmPassword': '123456',
                'reason': '需要使用后台功能',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_application_rejects_short_password(self):
        client = APIClient()
        response = client.post(
            '/api/v1/auth/account-applications/',
            {
                'username': 'shortpwd',
                'applicantName': '短密码',
                'enterpriseName': '某企业',
                'phone': '13800138011',
                'password': 'a1b',
                'confirmPassword': 'a1b',
                'reason': '需要使用后台功能',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_application_rejects_password_mismatch(self):
        client = APIClient()
        response = client.post(
            '/api/v1/auth/account-applications/',
            {
                'username': 'mismatchuser',
                'applicantName': '密码不一致',
                'enterpriseName': '某企业',
                'phone': '13800138012',
                'password': 'aaa-bbb-1',
                'confirmPassword': 'aaa-bbb-2',
                'reason': '需要使用后台功能',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_application_rejects_username_with_special_chars(self):
        client = APIClient()
        response = client.post(
            '/api/v1/auth/account-applications/',
            {
                'username': 'user_name',
                'applicantName': '特殊字符用户名',
                'enterpriseName': '某企业',
                'phone': '13800138013',
                'password': 'good-pass-1',
                'confirmPassword': 'good-pass-1',
                'reason': '需要使用后台功能',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_application_accepts_username_with_letters_and_digits(self):
        client = APIClient()
        with patch('apps.accounts.views.notify_account_application.delay'):
            response = client.post(
                '/api/v1/auth/account-applications/',
                {
                    'username': 'user123',
                    'applicantName': '字母数字用户名',
                    'enterpriseName': '某企业',
                    'phone': '13800138014',
                    'password': 'good-pass-1',
                    'confirmPassword': 'good-pass-1',
                    'reason': '需要使用后台功能',
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['username'], 'user123')

    def test_account_application_rejects_duplicate_username(self):
        AccountApplication.objects.create(
            username='dupuser',
            applicant_name='占位',
            enterprise_name='占位企业',
            phone='13800138020',
            password=make_password('seed-pass-1'),
            reason='占位',
        )
        client = APIClient()
        response = client.post(
            '/api/v1/auth/account-applications/',
            {
                'username': 'dupuser',
                'applicantName': '重名申请',
                'enterpriseName': '某企业',
                'phone': '13800138021',
                'password': 'good-pass-1',
                'confirmPassword': 'good-pass-1',
                'reason': '需要使用后台功能',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approved_application_uses_requested_username_for_login(self):
        from django.contrib.auth.hashers import make_password
        application = AccountApplication.objects.create(
            username='approveduser',
            applicant_name='审核通过用户',
            enterprise_name='通过企业',
            phone='13800138002',
            password=make_password('approved-pass-1'),
            reason='需要使用后台功能',
        )

        application.status = AccountApplication.STATUS_APPROVED
        application.save()

        user = User.objects.get(username='approveduser')
        self.assertTrue(user.check_password('approved-pass-1'))

        response = self.client.post(
            '/api/v1/auth/login/',
            {'username': 'approveduser', 'password': 'approved-pass-1'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'approveduser')

    def test_resaving_approved_application_repairs_missing_login_user(self):
        from django.contrib.auth.hashers import make_password
        application = AccountApplication.objects.create(
            username='repairuser',
            applicant_name='补建账号用户',
            enterprise_name='补建企业',
            phone='13800138004',
            password=make_password('repair-pass-1'),
            reason='需要使用后台功能',
        )
        application.status = AccountApplication.STATUS_APPROVED
        application.save()
        User.objects.filter(username='repairuser').delete()

        application.save()

        user = User.objects.get(username='repairuser')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('repair-pass-1'))

    def test_notify_account_application_task_sends_feishu_message(self):
        from django.contrib.auth.hashers import make_password
        application = AccountApplication.objects.create(
            username='feishuuser',
            applicant_name='飞书通知用户',
            enterprise_name='飞书企业',
            phone='13800138003',
            password=make_password('feishu-pass-1'),
            reason='需要使用后台功能',
        )

        with patch('apps.accounts.services.notifications.send_feishu_text', return_value=True) as send_text:
            result = notify_account_application(application.id)

        self.assertEqual(result, f'account_application_notified:{application.id}:True')
        send_text.assert_called_once()
        sent_text = send_text.call_args.args[0]
        self.assertIn('企业名称：飞书企业', sent_text)
        self.assertNotIn('企业邮箱', sent_text)

    def test_account_application_review_sends_feishu_notification_with_operator(self):
        from django.contrib.auth.hashers import make_password
        reviewer = User.objects.create_user(username='solin', password='test123456')
        role = Role.objects.create(name='reviewer', code='reviewer')
        permission, _ = PermissionPoint.objects.update_or_create(
            code='account_applications.review',
            defaults={
                'name': 'review applications',
                'module': 'account_applications',
                'description': 'review applications',
                'is_active': True,
            },
        )
        role.permission_points.add(permission)
        UserRole.objects.create(user=reviewer, role=role)
        application = AccountApplication.objects.create(
            username='reviewtarget',
            applicant_name='审核通知用户',
            enterprise_name='审核企业',
            phone='13800138005',
            password=make_password('review-pass-1'),
            reason='需要使用后台功能',
        )
        self.client.force_authenticate(user=reviewer)

        with patch('apps.resources.services.feishu.send_feishu_text', return_value=True) as send_text:
            response = self.client.patch(
                f'/api/v1/auth/account-applications/manage/{application.id}/',
                {'status': AccountApplication.STATUS_APPROVED},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent_text = send_text.call_args.args[0]
        self.assertIn('账号申请审核通知', sent_text)
        self.assertIn('操作人：solin', sent_text)
        self.assertIn('登录用户名：reviewtarget', sent_text)


class ChangePasswordApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='password-user', password='oldPass123456')
        self.client.force_authenticate(user=self.user)

    def test_change_password_updates_password(self):
        response = self.client.post(
            '/api/v1/auth/change-password/',
            {
                'oldPassword': 'oldPass123456',
                'newPassword': 'newPass123456',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newPass123456'))

    def test_change_password_rejects_wrong_old_password(self):
        response = self.client.post(
            '/api/v1/auth/change-password/',
            {
                'oldPassword': 'wrongPass123456',
                'newPassword': 'newPass123456',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldPass123456'))


class UserAdminPasswordResetEntryTests(APITestCase):
    """B1: 用户列表页直接出现"重置密码"入口列。"""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='boss', password='boss-pass-1', email='boss@example.com'
        )
        self.target = User.objects.create_user(
            username='victim', password='old-pass-1', email='victim@example.com'
        )
        self.client.force_login(self.admin)

    def test_user_admin_list_page_shows_reset_password_action_column(self):
        # 用户列表通过 AccountUser proxy 挂在"账号管理"分组下
        response = self.client.get('/admin/accounts/accountuser/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode('utf-8')
        # 列名出现
        self.assertIn('重置密码', body)
        # 列里渲染出指向该用户密码修改页的链接
        expected_href = f'/admin/accounts/accountuser/{self.target.id}/password/'
        self.assertIn(expected_href, body)

    def test_reset_password_link_target_page_is_reachable(self):
        response = self.client.get(
            f'/admin/accounts/accountuser/{self.target.id}/password/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_admin_grouped_under_accounts_app(self):
        # 在 admin 首页应能在"账号管理"分组里看到 User 入口
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode('utf-8')
        self.assertIn('/admin/accounts/accountuser/', body)

    def test_legacy_auth_user_changelist_no_longer_registered(self):
        # auth.User 仍注册（UserRoleAdmin.autocomplete_fields 依赖之，admin.E039），
        # 但已通过 SIMPLEUI_CONFIG.menu_display 白名单从左侧菜单中移除，
        # 真正暴露给运维使用的入口是 /admin/accounts/user/。
        from django.conf import settings
        self.assertNotIn('认证和授权', settings.SIMPLEUI_CONFIG['menu_display'])
