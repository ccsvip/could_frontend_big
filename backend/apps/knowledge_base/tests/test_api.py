from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shutil
import tempfile
import zipfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from kombu.exceptions import OperationalError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk, KnowledgeMediaAsset
from apps.resources.models import Resource
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


def build_document_upload(name: str = '知识库文档.pdf', content: bytes = b'knowledge-base-document') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type='application/octet-stream')


class KnowledgeBaseApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()
        self.override_cache = override_settings(
            CACHES={
                'default': {
                    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                    'LOCATION': 'knowledge-base-tests',
                }
            }
        )
        self.override_cache.enable()
        self.user = User.objects.create_user(username='knowledge-user', password='test123456', first_name='知识库用户')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='知识库测试角色', code='knowledge_role')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.override_cache.disable()
        self.override_media_root.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'knowledge_base',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def create_document(self, *, name: str = '文档一.pdf', title: str | None = None, content: bytes = b'doc-1') -> KnowledgeDocument:
        return KnowledgeDocument.objects.create(
            title=title or name.rsplit('.', 1)[0],
            file=build_document_upload(name=name, content=content),
            uploaded_by=self.user,
            tenant=self.tenant,
        )

    def create_base(self, *, name: str = '售后知识库') -> KnowledgeBase:
        return KnowledgeBase.objects.create(
            name=name,
            description='测试知识库',
            created_by=self.user,
            tenant=self.tenant,
        )

    def test_list_requires_view_permission(self):
        self.tenant.permission_points.clear()

        response = self.client.get('/api/v1/knowledge-base/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_document_returns_raw_drf_shape(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')

        response = self.client.post(
            '/api/v1/knowledge-base/',
            {
                'file': build_document_upload(name='培训资料.pdf', content=b'pdf-content'),
                'description': '新上传文档',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('status', response.data)
        self.assertNotIn('message', response.data)
        self.assertEqual(response.data['title'], '培训资料')
        self.assertEqual(response.data['fileName'], '培训资料.pdf')
        self.assertEqual(response.data['fileExtension'], 'pdf')
        self.assertNotIn('processingStatus', response.data)
        self.assertNotIn('processingStatusLabel', response.data)
        self.assertNotIn('processingResult', response.data)
        self.assertIn(response.data['indexingStatus'], {'pending', 'ready'})
        self.assertIn('chunkCount', response.data)
        self.assertEqual(response.data['uploadedBy'], '知识库用户')
        self.assertEqual(response.data['downloadCount'], 0)

    def test_create_document_sync_fallback_builds_keyword_index(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')

        with patch(
            'apps.knowledge_base.views.build_knowledge_document_index.delay',
            side_effect=OperationalError('broker unavailable'),
        ):
            response = self.client.post(
                '/api/v1/knowledge-base/',
                {
                    'file': build_document_upload(name='索引文档.txt', content='退款政策\n七天内可退款'.encode()),
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['indexingStatus'], 'ready')
        self.assertEqual(response.data['indexModel'], 'keyword')
        self.assertGreaterEqual(response.data['chunkCount'], 1)
        self.assertTrue(
            KnowledgeDocumentChunk.objects.filter(
                document_id=response.data['id'],
                embedding_model='keyword',
                content__contains='七天内可退款',
            ).exists()
        )

    def test_create_knowledge_base_returns_index_config(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')

        response = self.client.post(
            '/api/v1/knowledge-bases/',
            {
                'name': '索引配置知识库',
                'description': '可调切片',
                'chunkSize': 300,
                'chunkOverlap': 30,
                'retrievalTopN': 8,
                'retrievalMinScore': 0.35,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['chunkSize'], 300)
        self.assertEqual(response.data['chunkOverlap'], 30)
        self.assertEqual(response.data['retrievalTopN'], 8)
        self.assertEqual(response.data['retrievalMinScore'], 0.35)

    def test_create_knowledge_base_rejects_invalid_chunk_overlap(self):
        self.grant_permissions('knowledge_base.upload')

        response = self.client.post(
            '/api/v1/knowledge-bases/',
            {
                'name': '错误切片配置',
                'chunkSize': 200,
                'chunkOverlap': 200,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('分块重叠必须小于分块长度', response.data['message'])

    def test_knowledge_base_chunk_config_controls_index_segments(self):
        self.grant_permissions('knowledge_base.upload')
        knowledge_base = KnowledgeBase.objects.create(
            name='短分块知识库',
            chunk_size=100,
            chunk_overlap=20,
            retrieval_top_n=4,
            created_by=self.user,
            tenant=self.tenant,
        )

        with patch(
            'apps.knowledge_base.views.build_knowledge_document_index.delay',
            side_effect=OperationalError('broker unavailable'),
        ):
            response = self.client.post(
                f'/api/v1/knowledge-bases/{knowledge_base.id}/documents/',
                {
                    'file': build_document_upload(name='长文本.txt', content=b'abcdefghijklmnopqrstuvwxyz' * 10),
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['indexingStatus'], 'ready')
        self.assertEqual(response.data['chunkCount'], 4)
        chunks = list(
            KnowledgeDocumentChunk.objects.filter(document_id=response.data['id'])
            .order_by('chunk_index')
            .values_list('content', flat=True)
        )
        self.assertEqual([len(chunk) for chunk in chunks], [100, 100, 100, 20])

    def test_create_document_sends_feishu_notification(self):
        self.grant_permissions('knowledge_base.upload')

        with patch('apps.resources.services.feishu.send_feishu_card', return_value=True) as send_card:
            response = self.client.post(
                '/api/v1/knowledge-base/',
                {
                    'file': build_document_upload(name='通知文档.pdf', content=b'pdf-content'),
                    'description': '新增通知文档',
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_card.assert_called_once()
        sent_card = send_card.call_args.args[0]
        self.assertIn('知识库文档操作通知', str(sent_card))
        self.assertIn('通知文档.pdf', str(sent_card))
        self.assertIn(self.tenant.name, str(sent_card))

    def test_create_document_rejects_unsupported_extension(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')

        response = self.client.post(
            '/api/v1/knowledge-base/',
            {
                'file': build_document_upload(name='not-allowed.exe', content=b'boom'),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '仅支持 doc/docx/ppt/pptx/md/txt/pdf/xls/xlsx 等文档格式')

    def test_delete_document_requires_upload_permission(self):
        self.grant_permissions('knowledge_base.view')
        document = self.create_document(name='待删除文档.pdf', content=b'delete-me')

        response = self.client.delete(f'/api/v1/knowledge-base/{document.id}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(KnowledgeDocument.objects.filter(pk=document.pk).exists())

    def test_delete_document_removes_record_and_file(self):
        self.grant_permissions('knowledge_base.upload')
        document = self.create_document(name='待删除文档.pdf', content=b'delete-me')
        file_path = document.file.path

        with patch('apps.resources.services.feishu.send_feishu_card', return_value=True) as send_card:
            response = self.client.delete(f'/api/v1/knowledge-base/{document.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(KnowledgeDocument.objects.filter(pk=document.pk).exists())
        self.assertFalse(Path(file_path).exists())
        self.assertIn('待删除文档.pdf', str(send_card.call_args.args[0]))

    def test_download_returns_binary_response_and_increments_count(self):
        self.grant_permissions('knowledge_base.download')
        document = self.create_document(name='下载文档.pdf', content=b'download-me')

        with patch('apps.resources.services.feishu.send_feishu_card', return_value=True) as send_card:
            response = self.client.get(f'/api/v1/knowledge-base/{document.id}/download/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment; filename*=UTF-8''", response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'download-me')
        document.refresh_from_db()
        self.assertEqual(document.download_count, 1)
        self.assertIn('下载文档.pdf', str(send_card.call_args.args[0]))

    def test_bulk_download_deduplicates_and_renames_duplicate_file_names(self):
        self.grant_permissions('knowledge_base.bulk_download')
        first = self.create_document(name='重复文档.pdf', title='重复文档A', content=b'first-doc')
        second = self.create_document(name='重复文档.pdf', title='重复文档B', content=b'second-doc')

        with patch('apps.resources.services.feishu.send_feishu_card', return_value=True) as send_card:
            response = self.client.post(
                '/api/v1/knowledge-base/bulk-download/',
                {'ids': [first.id, first.id, second.id]},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        archive_bytes = b''.join(response.streaming_content)
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            self.assertCountEqual(archive.namelist(), ['重复文档.pdf', '重复文档(1).pdf'])
            self.assertEqual(archive.read('重复文档.pdf'), b'first-doc')
            self.assertEqual(archive.read('重复文档(1).pdf'), b'second-doc')

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.download_count, 1)
        self.assertEqual(second.download_count, 1)
        sent_card = send_card.call_args.args[0]
        self.assertIn('批量下载', str(sent_card))
        self.assertIn('文档数量', str(sent_card))

    def test_bulk_download_requires_at_least_one_valid_document(self):
        self.grant_permissions('knowledge_base.bulk_download')

        response = self.client.post('/api/v1/knowledge-base/bulk-download/', {'ids': ['bad', 9999]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '请至少选择一个有效文档')

    def test_bulk_download_enforces_count_limit(self):
        self.grant_permissions('knowledge_base.bulk_download')
        documents = [self.create_document(name=f'文档{i}.pdf', content=f'doc-{i}'.encode()) for i in range(21)]

        response = self.client.post(
            '/api/v1/knowledge-base/bulk-download/',
            {'ids': [document.id for document in documents]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '单次最多下载 20 个文档')

    def test_bulk_download_enforces_total_size_limit(self):
        self.grant_permissions('knowledge_base.bulk_download')
        first = self.create_document(name='超大文档一.pdf', content=b'a')
        second = self.create_document(name='超大文档二.pdf', content=b'b')
        KnowledgeDocument.objects.filter(pk=first.pk).update(file_size=120 * 1024 * 1024)
        KnowledgeDocument.objects.filter(pk=second.pk).update(file_size=90 * 1024 * 1024 + 1)

        response = self.client.post(
            '/api/v1/knowledge-base/bulk-download/',
            {'ids': [first.id, second.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '所选文档总大小不能超过 200MB')

    def test_processing_status_is_not_part_of_document_api(self):
        self.grant_permissions('knowledge_base.view')
        document = self.create_document(name='只读文档.pdf', content=b'read-only')

        response = self.client.get(f'/api/v1/knowledge-base/{document.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('processingStatus', response.data)
        self.assertNotIn('processingStatusLabel', response.data)
        self.assertNotIn('processingResult', response.data)

    def test_rebuild_document_index_requires_upload_permission(self):
        self.grant_permissions('knowledge_base.view')
        document = self.create_document(name='待重建.txt', content=b'rebuild-me')

        response = self.client.post(f'/api/v1/knowledge-base/{document.id}/index/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rebuild_document_index_queues_task(self):
        self.grant_permissions('knowledge_base.upload')
        document = self.create_document(name='待重建.txt', content=b'rebuild-me')

        with patch('apps.knowledge_base.views.build_knowledge_document_index.delay') as delay:
            response = self.client.post(f'/api/v1/knowledge-base/{document.id}/index/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['documentId'], document.id)
        self.assertTrue(response.data['queued'])
        delay.assert_called_once_with(document.id, force=True)
        document.refresh_from_db()
        self.assertEqual(document.index_status, KnowledgeDocument.IndexStatus.PENDING)

    def test_rebuild_knowledge_base_index_queues_all_documents(self):
        self.grant_permissions('knowledge_base.upload')
        knowledge_base = self.create_base()
        first = self.create_document(name='第一份.txt', content=b'first')
        second = self.create_document(name='第二份.txt', content=b'second')
        first.knowledge_base = knowledge_base
        first.save(update_fields=['knowledge_base'])
        second.knowledge_base = knowledge_base
        second.save(update_fields=['knowledge_base'])
        image = Resource.objects.create(
            tenant=self.tenant,
            name='展厅导览图',
            resource_type=Resource.TYPE_IMAGE,
        )
        asset = KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='展厅导览图',
            embedding_status=KnowledgeMediaAsset.EmbeddingStatus.READY,
        )

        with (
            patch('apps.knowledge_base.views.build_knowledge_document_index.delay') as document_delay,
            patch('apps.knowledge_base.views.build_knowledge_media_asset_index.delay') as media_asset_delay,
        ):
            response = self.client.post(f'/api/v1/knowledge-bases/{knowledge_base.id}/index/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['queuedCount'], 3)
        self.assertEqual(len(response.data['documents']), 2)
        self.assertEqual(len(response.data['mediaAssets']), 1)
        self.assertEqual(document_delay.call_count, 2)
        media_asset_delay.assert_called_once_with(asset.id, force=True)
        asset.refresh_from_db()
        self.assertEqual(asset.embedding_status, KnowledgeMediaAsset.EmbeddingStatus.PENDING)

    def test_create_media_assets_binds_existing_resources_to_knowledge_base(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')
        knowledge_base = self.create_base()
        image = Resource.objects.create(
            tenant=self.tenant,
            name='展厅导览图',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            description='一楼展厅参观路线',
        )
        video = Resource.objects.create(
            tenant=self.tenant,
            name='设备演示视频',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_HORIZONTAL,
            cloud_url='https://example.com/demo.mp4',
        )

        response = self.client.post(
            f'/api/v1/knowledge-bases/{knowledge_base.id}/media-assets/',
            {'resourceIds': [image.id, video.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)
        self.assertEqual({item['resourceId'] for item in response.data}, {image.id, video.id})
        first = response.data[0]
        self.assertIn(first['resourceType'], {'image', 'video'})
        self.assertTrue(first['isEnabled'])
        self.assertIn(first['resourceName'], first['description'])
        self.assertEqual(KnowledgeMediaAsset.objects.filter(knowledge_base=knowledge_base).count(), 2)

    def test_create_media_assets_rejects_cross_tenant_resource(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')
        knowledge_base = self.create_base()
        other_tenant = Tenant.objects.create(name='其他公司', code='other-tenant')
        other_resource = Resource.objects.create(
            tenant=other_tenant,
            name='其他公司图片',
            resource_type=Resource.TYPE_IMAGE,
        )

        response = self.client.post(
            f'/api/v1/knowledge-bases/{knowledge_base.id}/media-assets/',
            {'resourceIds': [other_resource.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(KnowledgeMediaAsset.objects.filter(knowledge_base=knowledge_base).exists())

    def test_update_media_asset_keeps_search_metadata_on_binding(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')
        knowledge_base = self.create_base()
        resource = Resource.objects.create(
            tenant=self.tenant,
            name='展厅导览图',
            resource_type=Resource.TYPE_IMAGE,
        )
        asset = KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=resource,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='展厅导览图',
            keywords='展厅',
            description='旧说明',
        )

        response = self.client.patch(
            f'/api/v1/knowledge-bases/{knowledge_base.id}/media-assets/{asset.id}/',
            {'keywords': '展厅 路线 入口', 'description': '一楼展厅导览路线图', 'isEnabled': False, 'priority': 7},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        resource.refresh_from_db()
        self.assertEqual(asset.keywords, '展厅 路线 入口')
        self.assertEqual(asset.description, '一楼展厅导览路线图')
        self.assertFalse(asset.is_enabled)
        self.assertEqual(asset.priority, 7)
        self.assertEqual(resource.description, '')

    def test_recall_test_returns_matching_media_assets_after_text_recall(self):
        self.grant_permissions('knowledge_base.view')
        knowledge_base = self.create_base(name='展厅知识库')
        document = self.create_document(
            name='展厅导览.txt',
            title='展厅导览',
            content='参观者从展厅入口进入后，可以按照导览路线依次参观产品区。'.encode(),
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        KnowledgeDocumentChunk.objects.create(
            tenant=self.tenant,
            document=document,
            chunk_index=0,
            content='参观者从展厅入口进入后，可以按照导览路线依次参观产品区。',
            content_hash='route',
            embedding_model='keyword',
        )
        guide_image = Resource.objects.create(
            tenant=self.tenant,
            name='展厅导览图',
            resource_type=Resource.TYPE_IMAGE,
            description='展厅路线图片',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=guide_image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='展厅导览图',
            keywords='展厅 导览 路线 入口',
            description='一楼展厅路线图',
        )
        Resource.objects.create(
            tenant=self.tenant,
            name='售后维修视频',
            resource_type=Resource.TYPE_VIDEO,
            cloud_url='https://example.com/repair.mp4',
        )

        response = self.client.post(
            f'/api/v1/knowledge-bases/{knowledge_base.id}/recall-test/',
            {'query': '展厅怎么走？'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['mode'], 'keyword')
        self.assertEqual(len(response.data['chunks']), 1)
        self.assertEqual(len(response.data['mediaAssets']), 1)
        self.assertEqual(response.data['mediaAssets'][0]['resourceId'], guide_image.id)
        self.assertEqual(response.data['mediaAssets'][0]['resourceType'], 'image')
        self.assertGreater(response.data['mediaAssets'][0]['relevance'], 0)
