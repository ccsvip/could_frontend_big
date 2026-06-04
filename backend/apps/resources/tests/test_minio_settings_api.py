from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.resources.models import MinioConfig, Resource, TenantVideoQuota
from apps.tenants.models import Tenant

User = get_user_model()


class MinioSettingsApiTests(APITestCase):
    def test_superuser_can_read_and_update_minio_settings(self):
        user = User.objects.create_superuser(username='root', password='test123456')
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            '/api/v1/settings/minio/',
            {
                'endpoint': 'localhost:9000',
                'accessKey': 'access',
                'secretKey': 'secret',
                'bucketName': 'digital-human',
                'secure': False,
                'videoMaxSizeMB': 2048,
                'allowVideoCloudUrl': False,
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['endpoint'], 'localhost:9000')
        self.assertEqual(response.data['bucketName'], 'digital-human')
        self.assertFalse(response.data['allowVideoCloudUrl'])
        self.assertTrue(MinioConfig.objects.filter(pk=1, bucket_name='digital-human').exists())

    def test_non_superuser_cannot_read_minio_settings(self):
        user = User.objects.create_user(username='tenant-user', password='test123456')
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/v1/settings/minio/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(
        MINIO_ENDPOINT='localhost:9000',
        MINIO_ACCESS_KEY='env-access',
        MINIO_SECRET_KEY='env-secret',
        MINIO_BUCKET_NAME='digital-human',
        MINIO_SECURE=False,
        MINIO_VIDEO_MAX_SIZE_MB=1024,
    )
    def test_superuser_read_returns_effective_env_fallback_without_secret(self):
        user = User.objects.create_superuser(username='env-root', password='test123456')
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/v1/settings/minio/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['endpoint'], 'localhost:9000')
        self.assertEqual(response.data['accessKey'], 'env-access')
        self.assertEqual(response.data['bucketName'], 'digital-human')
        self.assertNotIn('secretKey', response.data)

    def test_superuser_can_configure_tenant_video_quota(self):
        user = User.objects.create_superuser(username='quota-root', password='test123456')
        tenant = Tenant.objects.create(name='Quota Tenant', code='quota-tenant')
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            '/api/v1/settings/minio/quotas/',
            {'items': [{'tenantId': tenant.id, 'quotaLimited': True, 'quotaMB': 512}]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        quota = TenantVideoQuota.objects.get(tenant=tenant)
        self.assertEqual(quota.quota_mb, 512)
        row = next(item for item in response.data['results'] if item['tenantId'] == tenant.id)
        self.assertTrue(row['quotaLimited'])
        self.assertEqual(row['quotaMB'], 512)

    def test_superuser_can_set_tenant_video_quota_unlimited(self):
        user = User.objects.create_superuser(username='quota-unlimited-root', password='test123456')
        tenant = Tenant.objects.create(name='Unlimited Tenant', code='unlimited-tenant')
        TenantVideoQuota.objects.create(tenant=tenant, quota_mb=128)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            '/api/v1/settings/minio/quotas/',
            {'items': [{'tenantId': tenant.id, 'quotaLimited': False, 'quotaMB': 128}]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        quota = TenantVideoQuota.objects.get(tenant=tenant)
        self.assertIsNone(quota.quota_mb)
        row = next(item for item in response.data['results'] if item['tenantId'] == tenant.id)
        self.assertFalse(row['quotaLimited'])
        self.assertIsNone(row['quotaMB'])

    def test_quota_list_includes_tenant_usage(self):
        user = User.objects.create_superuser(username='quota-list-root', password='test123456')
        tenant = Tenant.objects.create(name='Usage Tenant', code='usage-tenant')
        TenantVideoQuota.objects.create(tenant=tenant, quota_mb=1)
        Resource.objects.create(
            tenant=tenant,
            resource_type=Resource.TYPE_VIDEO,
            name='Video',
            category=Resource.CATEGORY_HORIZONTAL,
            object_key=f'tenants/{tenant.id}/videos/demo.mp4',
            object_size=256 * 1024,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/v1/settings/minio/quotas/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(item for item in response.data['results'] if item['tenantId'] == tenant.id)
        self.assertEqual(row['usedBytes'], 256 * 1024)
        self.assertEqual(row['remainingBytes'], 768 * 1024)
