from django.test import TestCase, override_settings
from unittest.mock import patch

from apps.resources.models import MinioConfig, Resource, TenantVideoQuota
from apps.resources.services.minio_client import (
    MinioConfigError,
    build_public_object_url,
    build_video_object_key,
    get_minio_settings,
    presign_video_put_url,
    validate_tenant_object_key,
)
from apps.tenants.models import Tenant


class MinioClientTests(TestCase):
    def test_resource_has_file_when_object_key_exists(self):
        resource = Resource(resource_type=Resource.TYPE_VIDEO, object_key='tenants/1/videos/demo.mp4')

        self.assertTrue(resource.has_file)

    def test_video_object_key_is_namespaced_by_tenant(self):
        tenant = Tenant.objects.create(name='Tenant A', code='tenant-a')

        object_key = build_video_object_key('demo video.mp4', tenant=tenant)

        self.assertRegex(object_key, rf'^tenants/{tenant.id}/videos/\d{{4}}/\d{{2}}/\d{{2}}/[0-9a-f-]+\.mp4$')

    def test_validate_tenant_object_key_rejects_other_tenant_prefix(self):
        tenant = Tenant.objects.create(name='Tenant A', code='tenant-a')
        other = Tenant.objects.create(name='Tenant B', code='tenant-b')

        with self.assertRaises(MinioConfigError):
            validate_tenant_object_key(f'tenants/{other.id}/videos/demo.mp4', tenant=tenant)

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
        MINIO_INTERNAL_ENDPOINT='',
    )
    def test_settings_fall_back_to_env(self):
        settings = get_minio_settings()

        self.assertEqual(settings.endpoint, 'localhost:9000')
        self.assertEqual(settings.internal_endpoint, 'localhost:9000')
        self.assertEqual(settings.bucket_name, 'digital-human')
        self.assertFalse(settings.secure)

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
    )
    def test_db_config_overrides_env_and_public_url_is_derived(self):
        MinioConfig.load()
        MinioConfig.objects.update(endpoint='storage.example.com:9000', bucket_name='tenant-videos', secure=True)

        settings = get_minio_settings()
        public_url = build_public_object_url('tenants/1/videos/demo.mp4', settings)

        self.assertEqual(settings.endpoint, 'storage.example.com:9000')
        self.assertEqual(settings.bucket_name, 'tenant-videos')
        self.assertEqual(public_url, 'https://storage.example.com:9000/tenant-videos/tenants/1/videos/demo.mp4')

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_INTERNAL_ENDPOINT='host.docker.internal:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
    )
    def test_presign_uses_internal_endpoint_for_bucket_check_only(self):
        tenant = Tenant.objects.create(name='Tenant A', code='tenant-a')
        endpoints = []

        class FakeClient:
            def __init__(self, endpoint):
                self.endpoint = endpoint

            def bucket_exists(self, bucket_name):
                return True

            def set_bucket_policy(self, bucket_name, policy):
                return None

            def presigned_put_object(self, bucket_name, object_name, expires):
                return f'http://{self.endpoint}/{bucket_name}/{object_name}'

        def fake_build_client(settings, *, endpoint=None):
            selected = endpoint or settings.endpoint
            endpoints.append(selected)
            return FakeClient(selected)

        with patch('apps.resources.services.minio_client._build_client', side_effect=fake_build_client):
            response = presign_video_put_url(
                filename='demo.mp4',
                content_type='video/mp4',
                file_size=1024,
                tenant=tenant,
            )

        self.assertEqual(endpoints, ['host.docker.internal:9000', 'localhost:9000'])
        self.assertTrue(response['uploadUrl'].startswith('http://localhost:9000/digital-human/'))

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_INTERNAL_ENDPOINT='host.docker.internal:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
    )
    def test_presign_rejects_when_tenant_video_quota_is_exhausted(self):
        tenant = Tenant.objects.create(name='Tenant A', code='tenant-a')
        TenantVideoQuota.objects.create(tenant=tenant, quota_mb=1)
        Resource.objects.create(
            tenant=tenant,
            resource_type=Resource.TYPE_VIDEO,
            name='Existing',
            category=Resource.CATEGORY_HORIZONTAL,
            object_key=f'tenants/{tenant.id}/videos/existing.mp4',
            object_size=900 * 1024,
        )

        with self.assertRaises(MinioConfigError):
            presign_video_put_url(
                filename='demo.mp4',
                content_type='video/mp4',
                file_size=200 * 1024,
                tenant=tenant,
            )

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_INTERNAL_ENDPOINT='host.docker.internal:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
    )
    def test_presign_allows_upload_when_tenant_video_quota_is_unlimited(self):
        tenant = Tenant.objects.create(name='Tenant A', code='tenant-a')
        TenantVideoQuota.objects.create(tenant=tenant, quota_mb=None)

        class FakeClient:
            def bucket_exists(self, bucket_name):
                return True

            def set_bucket_policy(self, bucket_name, policy):
                return None

            def presigned_put_object(self, bucket_name, object_name, expires):
                return f'http://localhost:9000/{bucket_name}/{object_name}'

        with patch('apps.resources.services.minio_client._build_client', return_value=FakeClient()):
            response = presign_video_put_url(
                filename='demo.mp4',
                content_type='video/mp4',
                file_size=200 * 1024,
                tenant=tenant,
            )

        self.assertFalse(response['quotaLimited'])
        self.assertIsNone(response['quotaMB'])
        self.assertEqual(response['objectSize'], 200 * 1024)
