import base64
import hashlib
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.app_updates.models import AppRelease, AppUpdateEvent
from apps.app_updates.signing import build_signature_payload
from apps.devices.models import Device
from apps.tenants.models import Membership, Tenant


APK_BYTES = b'fake-apk-content-for-tests'


def private_key_base64():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, base64.b64encode(pem).decode('ascii')


def make_release(*, version_code=10002, version_name='1.0.2', active=True, threshold=0, created_by=None):
    version_info = f'solin_cloud_{version_name}_20260720_1030'
    return AppRelease.objects.create(
        version_name=version_name,
        version_code=version_code,
        version_info=version_info,
        apk_file=SimpleUploadedFile(f'{version_info}.apk', APK_BYTES, content_type='application/vnd.android.package-archive'),
        force_upgrade_version_code=threshold,
        release_notes='修复已知问题',
        is_active=active,
        created_by=created_by,
    )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='app-update-tests-'))
class AppReleaseManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = get_user_model().objects.create_superuser('release-admin', password='pw123456')
        self.staff = get_user_model().objects.create_user('release-staff', password='pw123456', is_staff=True)
        self.tenant = Tenant.objects.create(name='测试公司', code='release-company')
        self.company_admin = get_user_model().objects.create_user('company-admin', password='pw123456')
        self.company_employee = get_user_model().objects.create_user('company-employee', password='pw123456')
        Membership.objects.create(user=self.company_admin, tenant=self.tenant, is_tenant_admin=True)
        Membership.objects.create(user=self.company_employee, tenant=self.tenant, is_tenant_admin=False)

    def upload_payload(self):
        version_info = 'solin_cloud_1.0.2_20260720_1030'
        return {
            'versionName': '1.0.2',
            'versionCode': 10002,
            'versionInfo': version_info,
            'apkFile': SimpleUploadedFile(f'{version_info}.apk', APK_BYTES, content_type='application/vnd.android.package-archive'),
            'forceUpgradeVersionCode': 10001,
            'releaseNotes': '首个升级版本',
            'isActive': True,
        }

    def test_superuser_can_upload_and_backend_derives_file_metadata(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.post('/api/v1/app-update-releases/', self.upload_payload(), format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        release = AppRelease.objects.get()
        self.assertEqual(release.file_name, 'solin_cloud_1.0.2_20260720_1030.apk')
        self.assertEqual(release.file_size, len(APK_BYTES))
        self.assertEqual(release.sha256, hashlib.sha256(APK_BYTES).hexdigest())
        self.assertEqual(release.created_by, self.superuser)

    def test_company_and_non_superuser_staff_cannot_access_management_api(self):
        release = make_release(created_by=self.superuser)
        detail = f'/api/v1/app-update-releases/{release.release_id}/'
        for user in (self.company_admin, self.company_employee, self.staff):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/v1/app-update-releases/').status_code, 403)
            payload = self.upload_payload()
            self.assertEqual(self.client.post('/api/v1/app-update-releases/', payload, format='multipart').status_code, 403)
            self.assertEqual(self.client.get(detail).status_code, 403)
            self.assertEqual(self.client.patch(detail, {'isActive': False}, format='json').status_code, 403)

    def test_django_admin_is_also_restricted_to_superusers(self):
        model_admin = django_admin.site._registry[AppRelease]
        request = RequestFactory().get('/admin/app_updates/apprelease/')
        request.user = self.staff
        self.assertFalse(model_admin.has_module_permission(request))
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))

        request.user = self.superuser
        self.assertTrue(model_admin.has_module_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertTrue(model_admin.has_add_permission(request))
        self.assertTrue(model_admin.has_change_permission(request))

    def test_release_only_allows_active_patch_and_no_delete(self):
        release = make_release(created_by=self.superuser)
        self.client.force_authenticate(self.superuser)
        detail = f'/api/v1/app-update-releases/{release.release_id}/'
        response = self.client.patch(detail, {'isActive': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        release.refresh_from_db()
        self.assertFalse(release.is_active)
        self.assertEqual(self.client.patch(detail, {'releaseNotes': '篡改'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(detail).status_code, 405)

    def test_model_rejects_file_replacement_and_invalid_filename(self):
        release = make_release(created_by=self.superuser)
        release.release_notes = '不允许修改'
        with self.assertRaises(ValidationError):
            release.save()
        with self.assertRaises(ValidationError):
            AppRelease.objects.create(
                version_name='1.0.3', version_code=10003,
                version_info='solin_cloud_1.0.3_20260720_1030',
                apk_file=SimpleUploadedFile('wrong.apk', APK_BYTES),
            )

    def test_duplicate_version_fields_return_validation_errors(self):
        self.client.force_authenticate(self.superuser)
        first = self.client.post('/api/v1/app-update-releases/', self.upload_payload(), format='multipart')
        self.assertEqual(first.status_code, 201, first.data)

        duplicate_code = self.upload_payload()
        duplicate_code['versionInfo'] = 'solin_cloud_1.0.3_20260720_1030'
        duplicate_code['apkFile'] = SimpleUploadedFile(
            'solin_cloud_1.0.3_20260720_1030.apk', APK_BYTES,
            content_type='application/vnd.android.package-archive',
        )
        response = self.client.post('/api/v1/app-update-releases/', duplicate_code, format='multipart')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('versionCode', response.data['details'])

        duplicate_info = self.upload_payload()
        duplicate_info['versionCode'] = 10003
        response = self.client.post('/api/v1/app-update-releases/', duplicate_info, format='multipart')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('versionInfo', response.data['details'])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='app-update-device-tests-'))
class AppUpdateDeviceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name='设备公司', code='device-update-company')
        self.device = Device.objects.create(code='ANDROID-UPDATE-001', name='升级设备', tenant=self.tenant)
        self.private_key, self.encoded_private_key = private_key_base64()

    def check(self, version_code=10001, **headers):
        return self.client.post(
            '/api/v1/app-updates/check/',
            {
                'packageName': 'com.solin.digital',
                'versionName': '1.0.1',
                'versionCode': version_code,
                'versionInfo': 'solin_cloud_1.0.1_20260718_0930',
            },
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-UPDATE-001',
            **headers,
        )

    def test_no_release_and_current_version_return_no_update(self):
        response = self.check()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['release'], None)
        self.assertFalse(response.data['hasUpdate'])
        make_release(version_code=10002, threshold=10001)
        response = self.check(version_code=10002)
        self.assertFalse(response.data['hasUpdate'])
        self.assertEqual(response.data['forceUpgradeVersionCode'], 10001)

    def test_newer_release_response_has_verifiable_signature(self):
        release = make_release(threshold=10001)
        with self.settings(APP_UPDATE_PRIVATE_KEY_BASE64=self.encoded_private_key):
            response = self.check(HTTP_X_REQUEST_ID='req-update', HTTP_X_TRACE_ID='trace-update')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['hasUpdate'])
        self.assertEqual(response.data['requestId'], 'req-update')
        payload = response.data['release']
        canonical = build_signature_payload(
            release,
            download_url=payload['downloadUrl'],
            force_upgrade_version_code=response.data['forceUpgradeVersionCode'],
            expires_at=payload['expiresAt'],
        )
        self.private_key.public_key().verify(
            base64.b64decode(payload['signature']), canonical.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256(),
        )

    def test_missing_key_returns_503_only_when_update_exists(self):
        make_release()
        response = self.check()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 'UPDATE_SIGNING_UNAVAILABLE')

    def test_invalid_device_and_package_are_rejected(self):
        response = self.client.post('/api/v1/app-updates/check/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            '/api/v1/app-updates/check/',
            {'packageName': 'other.package', 'versionName': '1', 'versionCode': 1, 'versionInfo': 'x'},
            format='json', HTTP_X_DEVICE_CODE=self.device.code,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'INVALID_REQUEST')

    def test_full_and_range_download(self):
        release = make_release()
        url = f'/api/v1/app-update-releases/{release.release_id}/apk/'
        full = self.client.get(url)
        self.assertEqual(full.status_code, 200)
        self.assertEqual(b''.join(full.streaming_content), APK_BYTES)
        partial = self.client.get(url, HTTP_RANGE='bytes=5-11')
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial['Content-Range'], f'bytes 5-11/{len(APK_BYTES)}')
        self.assertEqual(b''.join(partial.streaming_content), APK_BYTES[5:12])
        invalid = self.client.get(url, HTTP_RANGE='bytes=999-1000')
        self.assertEqual(invalid.status_code, 416)

    def test_inactive_release_cannot_download(self):
        release = make_release(active=False)
        response = self.client.get(f'/api/v1/app-update-releases/{release.release_id}/apk/')
        self.assertEqual(response.status_code, 404)

    def test_report_accepts_all_states_and_rejects_unknown_state(self):
        release = make_release()
        payload = self.report_payload(release)
        for state in AppUpdateEvent.State.values:
            payload['state'] = state
            response = self.client.post(
                '/api/v1/app-updates/report/', payload, format='json', HTTP_X_DEVICE_CODE=self.device.code,
            )
            self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            set(AppUpdateEvent.objects.values_list('state', flat=True)),
            set(AppUpdateEvent.State.values),
        )
        payload['state'] = 'UNKNOWN'
        self.assertEqual(
            self.client.post('/api/v1/app-updates/report/', payload, format='json', HTTP_X_DEVICE_CODE=self.device.code).status_code,
            400,
        )

    def test_report_rejects_inconsistent_versions(self):
        release = make_release()
        payload = self.report_payload(release)
        payload['targetVersionCode'] = release.version_code + 1
        response = self.client.post(
            '/api/v1/app-updates/report/', payload, format='json', HTTP_X_DEVICE_CODE=self.device.code,
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('targetVersionCode', response.data['details'])

    @staticmethod
    def report_payload(release):
        return {
            'releaseId': release.release_id,
            'packageName': release.package_name,
            'currentVersionCode': 10001,
            'targetVersionCode': release.version_code,
            'state': 'VERIFIED',
            'message': '',
            'occurredAt': timezone.now().isoformat(),
        }
