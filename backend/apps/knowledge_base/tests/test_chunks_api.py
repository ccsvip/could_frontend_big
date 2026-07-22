from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import BailianKnowledgeConfig, TenantKnowledgeModelSettings
from apps.knowledge_base import bailian
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class KnowledgeDocumentChunkApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chunk-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='切片角色', code='chunk_role')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

        BailianKnowledgeConfig.objects.update_or_create(
            pk=1,
            defaults={
                'access_key_id': 'ak',
                'access_key_secret_encrypted': 'encrypted',
                'workspace_id': 'ws-1',
                'is_active': True,
            },
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            managed_rag_enabled=True,
            is_active=True,
        )
        self.knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='切片知识库',
            bailian_index_id='index-1',
            bailian_index_status='COMPLETED',
        )
        self.document = KnowledgeDocument.objects.create(
            tenant=self.tenant,
            uploaded_by=self.user,
            knowledge_base=self.knowledge_base,
            title='手册',
            file=SimpleUploadedFile('manual.pdf', b'pdf-bytes'),
            index_status=KnowledgeDocument.IndexStatus.READY,
            bailian_file_id='file-1',
        )

    def grant_permissions(self, *codes: str):
        points = []
        for code in codes:
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'knowledge_base', 'description': code, 'is_active': True},
            )
            points.append(point)
        self.role.permission_points.set(points)
        self.tenant.permission_points.set(points)

    def test_list_chunks_success(self):
        self.grant_permissions('knowledge_base.view')
        remote = {
            'total': 1,
            'nodes': [
                {
                    'chunk_id': 'chunk-1',
                    'title': '标题',
                    'content': '切片正文内容足够长',
                    'is_displayed': True,
                }
            ],
        }
        with patch('apps.knowledge_base.views.bailian.list_chunks', return_value=remote) as list_mock:
            response = self.client.get(f'/api/v1/knowledge-base/{self.document.id}/chunks/?page=1&pageSize=10')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['chunkId'], 'chunk-1')
        self.assertEqual(response.data['results'][0]['content'], '切片正文内容足够长')
        list_mock.assert_called_once_with(index_id='index-1', file_id='file-1', page_num=1, page_size=10)

    def test_list_chunks_not_ready(self):
        self.grant_permissions('knowledge_base.view')
        self.document.index_status = KnowledgeDocument.IndexStatus.PENDING
        self.document.save(update_fields=['index_status'])

        response = self.client.get(f'/api/v1/knowledge-base/{self.document.id}/chunks/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_chunk_requires_upload_permission(self):
        self.grant_permissions('knowledge_base.view')
        response = self.client.patch(
            f'/api/v1/knowledge-base/{self.document.id}/chunks/chunk-1/',
            {'content': '这是一段足够长的切片正文内容', 'title': '新标题'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_chunk_success(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.upload')
        with patch('apps.knowledge_base.views.bailian.update_chunk') as update_mock:
            response = self.client.patch(
                f'/api/v1/knowledge-base/{self.document.id}/chunks/chunk-1/',
                {'content': '这是一段足够长的切片正文内容', 'title': '新标题'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['chunkId'], 'chunk-1')
        self.assertEqual(response.data['title'], '新标题')
        update_mock.assert_called_once_with(
            index_id='index-1',
            file_id='file-1',
            chunk_id='chunk-1',
            content='这是一段足够长的切片正文内容',
            title='新标题',
            is_displayed=True,
        )

    def test_list_chunks_tenant_isolation(self):
        self.grant_permissions('knowledge_base.view')
        other_tenant = Tenant.objects.create(name='其他公司', code='other-chunk')
        other_base = KnowledgeBase.objects.create(
            tenant=other_tenant,
            name='他库',
            bailian_index_id='index-other',
        )
        other_doc = KnowledgeDocument.objects.create(
            tenant=other_tenant,
            knowledge_base=other_base,
            title='他文档',
            file=SimpleUploadedFile('other.pdf', b'x'),
            index_status=KnowledgeDocument.IndexStatus.READY,
            bailian_file_id='file-other',
        )
        response = self.client.get(f'/api/v1/knowledge-base/{other_doc.id}/chunks/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_chunks_mapping(self):
        node = SimpleNamespace(
            text='正文',
            metadata={
                '_id': 'cid-1',
                'title': 't',
                'is_displayed_chunk_content': 'false',
            },
        )
        data = SimpleNamespace(nodes=[node], total=1)
        response = SimpleNamespace(body=SimpleNamespace(data=data, code='', message='', status='200'))
        with patch('apps.knowledge_base.bailian._client') as client_factory:
            client = client_factory.return_value[0]
            client.list_chunks.return_value = response
            client_factory.return_value = (client, SimpleNamespace(workspace_id='ws-1'))
            # re-patch properly
        with patch('apps.knowledge_base.bailian._client') as client_factory:
            client = client_factory.return_value[0]
            client_factory.return_value = (client, SimpleNamespace(workspace_id='ws-1'))
            client.list_chunks.return_value = response
            result = bailian.list_chunks(index_id='i', file_id='f', page_num=1, page_size=10)

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['nodes'][0]['chunk_id'], 'cid-1')
        self.assertEqual(result['nodes'][0]['is_displayed'], False)
