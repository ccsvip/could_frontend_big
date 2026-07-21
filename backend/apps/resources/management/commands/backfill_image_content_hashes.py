import hashlib

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.resources.models import Resource
from apps.resources.services.image_hashes import calculate_sha256
from apps.resources.services.minio_client import iter_object_chunks


class Command(BaseCommand):
    help = '为尚未索引的图片资源回填 SHA-256，保留并报告历史重复资源'

    def handle(self, *args, **options):
        resource_ids = list(
            Resource.objects.filter(resource_type=Resource.TYPE_IMAGE, content_hash='')
            .order_by('created_at', 'id')
            .values_list('id', flat=True)
        )
        indexed = 0
        duplicate = 0
        failed = 0

        for resource_id in resource_ids:
            resource = Resource.objects.get(id=resource_id)
            try:
                content_hash = self._calculate_resource_hash(resource)
                existing = (
                    Resource.objects.filter(
                        tenant_id=resource.tenant_id,
                        resource_type=Resource.TYPE_IMAGE,
                        content_hash=content_hash,
                    )
                    .exclude(id=resource.id)
                    .order_by('created_at', 'id')
                    .first()
                )

                if existing is not None and (existing.created_at, existing.id) < (resource.created_at, resource.id):
                    duplicate += 1
                    self.stdout.write(
                        f'DUPLICATE resource={resource.id} baseline={existing.id} hash={content_hash}'
                    )
                    continue

                try:
                    with transaction.atomic():
                        if existing is not None:
                            Resource.objects.filter(id=existing.id).update(content_hash='')
                        updated = Resource.objects.filter(id=resource.id, content_hash='').update(
                            content_hash=content_hash
                        )
                except IntegrityError:
                    baseline = Resource.objects.filter(
                        tenant_id=resource.tenant_id,
                        resource_type=Resource.TYPE_IMAGE,
                        content_hash=content_hash,
                    ).order_by('created_at', 'id').first()
                    duplicate += 1
                    self.stdout.write(
                        f'DUPLICATE resource={resource.id} baseline={baseline.id if baseline else "unknown"} '
                        f'hash={content_hash}'
                    )
                    continue

                if updated:
                    indexed += 1
                    self.stdout.write(f'INDEXED resource={resource.id} hash={content_hash}')
                    if existing is not None:
                        duplicate += 1
                        self.stdout.write(
                            f'DUPLICATE resource={existing.id} baseline={resource.id} hash={content_hash}'
                        )
            except Exception as exc:
                failed += 1
                self.stderr.write(f'FAILED resource={resource.id} error={exc}')

        self.stdout.write(
            self.style.SUCCESS(f'完成：indexed={indexed} duplicate={duplicate} failed={failed}')
        )

    @staticmethod
    def _calculate_resource_hash(resource: Resource) -> str:
        if resource.object_key:
            digest = hashlib.sha256()
            for chunk in iter_object_chunks(resource.object_key, backend=resource.storage_backend):
                digest.update(chunk)
            return digest.hexdigest()
        if resource.file:
            resource.file.open('rb')
            try:
                return calculate_sha256(resource.file)
            finally:
                resource.file.close()
        raise ValueError('图片没有可读取的文件或对象键')
