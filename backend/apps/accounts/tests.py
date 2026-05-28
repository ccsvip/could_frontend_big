from unittest.mock import patch

from django.contrib.auth import get_user_model
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
                    'username': 'apply-user',
                    'applicantName': '测试申请人',
                    'phone': '13800138000',
                    'email': 'tester@example.com',
                    'reason': '需要使用后台功能',
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['username'], 'apply-user')
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
                    'username': 'sync-notify-user',
                    'applicantName': '同步通知申请人',
                    'phone': '13800138001',
                    'email': 'sync@example.com',
                    'reason': '需要使用后台功能',
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notify_sync.assert_called_once()

    def test_approved_application_uses_requested_username_for_login(self):
        application = AccountApplication.objects.create(
            username='approved-user',
            applicant_name='审核通过用户',
            phone='13800138002',
            email='approved@example.com',
            reason='需要使用后台功能',
        )

        application.status = AccountApplication.STATUS_APPROVED
        application.save()

        user = User.objects.get(username='approved-user')
        self.assertEqual(user.email, 'approved@example.com')
        self.assertTrue(user.check_password('123456'))

        response = self.client.post(
            '/api/v1/auth/login/',
            {'username': 'approved-user', 'password': '123456'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'approved-user')

    def test_resaving_approved_application_repairs_missing_login_user(self):
        application = AccountApplication.objects.create(
            username='repair-user',
            applicant_name='补建账号用户',
            phone='13800138004',
            email='repair@example.com',
            reason='需要使用后台功能',
        )
        application.status = AccountApplication.STATUS_APPROVED
        application.save()
        User.objects.filter(username='repair-user').delete()

        application.save()

        user = User.objects.get(username='repair-user')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('123456'))

    def test_notify_account_application_task_sends_feishu_message(self):
        application = AccountApplication.objects.create(
            username='feishu-user',
            applicant_name='飞书通知用户',
            phone='13800138003',
            email='feishu@example.com',
            reason='需要使用后台功能',
        )

        with patch('apps.accounts.services.notifications.send_feishu_text', return_value=True) as send_text:
            result = notify_account_application(application.id)

        self.assertEqual(result, f'account_application_notified:{application.id}:True')
        send_text.assert_called_once()

    def test_account_application_review_sends_feishu_notification_with_operator(self):
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
            username='review-target',
            applicant_name='审核通知用户',
            phone='13800138005',
            email='review@example.com',
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
        self.assertIn('登录用户名：review-target', sent_text)


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
