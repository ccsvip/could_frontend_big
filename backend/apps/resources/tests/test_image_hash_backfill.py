import hashlib
from io import StringIO
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from apps.resources.models import Resource
from apps.tenants.models import Tenant


class ImageHashConstraintTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Tenant A', code='hash-tenant-a')
        self.other_tenant = Tenant.objects.create(name='Tenant B', code='hash-tenant-b')
        self.content_hash = hashlib.sha256(b'image').hexdigest()

    def create_resource(self, *, tenant, resource_type=Resource.TYPE_IMAGE):
        return Resource.objects.create(
            tenant=tenant,
            name='resource',
            resource_type=resource_type,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=self.content_hash,
        )

    def test_same_hash_is_allowed_for_different_tenants_and_videos(self):
        self.create_resource(tenant=self.tenant)
        self.create_resource(tenant=self.other_tenant)
        self.create_resource(tenant=self.tenant, resource_type=Resource.TYPE_VIDEO)

        self.assertEqual(Resource.objects.filter(content_hash=self.content_hash).count(), 3)

    def test_same_tenant_image_hash_is_unique(self):
        self.create_resource(tenant=self.tenant)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_resource(tenant=self.tenant)


class BackfillImageContentHashesTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Tenant A', code='backfill-tenant')
        self.media_root = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_root.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media_root.cleanup()

    def create_image(self, name: str, content: bytes):
        resource = Resource(
            tenant=self.tenant,
            name=name,
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
        )
        resource.file.save(f'{name}.png', ContentFile(content), save=True)
        return resource

    def test_command_indexes_first_resource_and_reports_duplicates_idempotently(self):
        content = b'same historical image'
        first = self.create_image('first', content)
        duplicate = self.create_image('duplicate', content)
        output = StringIO()

        call_command('backfill_image_content_hashes', stdout=output, stderr=output)

        first.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(first.content_hash, hashlib.sha256(content).hexdigest())
        self.assertEqual(duplicate.content_hash, '')
        self.assertIn(f'DUPLICATE resource={duplicate.id} baseline={first.id}', output.getvalue())
        self.assertIn('indexed=1 duplicate=1 failed=0', output.getvalue())

        second_output = StringIO()
        call_command('backfill_image_content_hashes', stdout=second_output, stderr=second_output)
        self.assertIn('indexed=0 duplicate=1 failed=0', second_output.getvalue())

    def test_command_continues_after_missing_file(self):
        Resource.objects.create(
            tenant=self.tenant,
            name='missing',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
        )
        valid = self.create_image('valid', b'valid image')
        output = StringIO()

        call_command('backfill_image_content_hashes', stdout=output, stderr=output)

        valid.refresh_from_db()
        self.assertTrue(valid.content_hash)
        self.assertIn('indexed=1 duplicate=0 failed=1', output.getvalue())

    def test_command_moves_hash_to_earliest_resource(self):
        content = b'historical image uploaded again'
        content_hash = hashlib.sha256(content).hexdigest()
        earliest = self.create_image('earliest', content)
        later = Resource.objects.create(
            tenant=self.tenant,
            name='later indexed upload',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=content_hash,
        )
        output = StringIO()

        call_command('backfill_image_content_hashes', stdout=output, stderr=output)

        earliest.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(earliest.content_hash, content_hash)
        self.assertEqual(later.content_hash, '')
        self.assertIn(f'DUPLICATE resource={later.id} baseline={earliest.id}', output.getvalue())
