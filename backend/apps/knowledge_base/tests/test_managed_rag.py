from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.ai_models.models import AgentApplication, TenantKnowledgeModelSettings
from apps.ai_models.services.agent_knowledge import retrieve_knowledge_chunks, retrieve_knowledge_context
from apps.knowledge_base import bailian
from apps.knowledge_base.managed_indexing import build_managed_document_index
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument
from apps.tenants.test_utils import TenantTestMixin


User = get_user_model()


@override_settings(BAILIAN_POLL_INTERVAL_SECONDS=0)
class ManagedRagTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='managed-rag-user', password='test123456')
        self.setup_tenant(self.user)
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            managed_rag_enabled=True,
            is_active=True,
        )
        self.knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='托管知识库',
            bailian_index_id='index-1',
            bailian_index_status='COMPLETED',
        )

    def create_document(self, name: str) -> KnowledgeDocument:
        return KnowledgeDocument.objects.create(
            tenant=self.tenant,
            uploaded_by=self.user,
            knowledge_base=self.knowledge_base,
            title=name.rsplit('.', 1)[0],
            file=SimpleUploadedFile(name, b'managed-rag-content'),
        )

    def test_bailian_business_error_preserves_code_and_message(self):
        response = SimpleNamespace(
            body=SimpleNamespace(
                data=None,
                code='NOT AUTHORIZED',
                status='401',
                message='Access denied: workspace is unavailable.',
            )
        )

        with self.assertRaisesMessage(
            bailian.BailianKnowledgeError,
            '百炼请求失败（NOT AUTHORIZED）：Access denied: workspace is unavailable.',
        ):
            bailian._data(response)

    def test_official_document_formats_use_managed_indexing(self):
        for suffix in ('pdf', 'docx', 'xlsx'):
            with self.subTest(suffix=suffix):
                document = self.create_document(f'document-{suffix}.{suffix}')
                with (
                    patch('apps.knowledge_base.managed_indexing.bailian.apply_upload_lease') as apply_lease,
                    patch('apps.knowledge_base.managed_indexing.bailian.upload_file'),
                    patch('apps.knowledge_base.managed_indexing.bailian.add_file', return_value=f'file-{suffix}'),
                    patch('apps.knowledge_base.managed_indexing.bailian.describe_file', return_value={'status': 'PARSE_SUCCESS', 'error': '', 'parser': 'AUTO_SELECT'}),
                    patch('apps.knowledge_base.managed_indexing.bailian.add_document_to_index', return_value=f'job-{suffix}'),
                    patch('apps.knowledge_base.managed_indexing.bailian.get_index_job_status', return_value='COMPLETED'),
                ):
                    apply_lease.return_value = bailian.UploadLease('lease-1', 'https://upload.invalid', 'PUT', {})
                    result = build_managed_document_index(document.id)

                document.refresh_from_db()
                self.assertEqual(result['status'], KnowledgeDocument.IndexStatus.READY)
                self.assertEqual(document.bailian_file_id, f'file-{suffix}')
                self.assertEqual(document.index_model, 'bailian-managed-rag')

    def test_retrieve_uses_bailian_and_injects_existing_context_contract(self):
        document = self.create_document('refund-policy.pdf')
        document.index_status = KnowledgeDocument.IndexStatus.READY
        document.bailian_file_id = 'file-refund'
        document.save(update_fields=['index_status', 'bailian_file_id', 'updated_at'])
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='托管知识智能体',
        )
        application.knowledge_bases.add(self.knowledge_base)
        nodes = [
            bailian.RetrievalNode(
                text='客户购买后七天内可以申请退款。',
                score=0.91,
                metadata={'file_id': 'file-refund'},
            )
        ]

        with (
            patch('apps.ai_models.services.agent_knowledge.bailian.retrieve', return_value=nodes) as retrieve_mock,
            patch('apps.ai_models.services.agent_knowledge.build_document_index') as local_index_mock,
            patch('apps.ai_models.services.agent_knowledge._embed_texts') as local_embedding_mock,
        ):
            result = retrieve_knowledge_chunks(query='退款规则是什么？', application=application)
            context = retrieve_knowledge_context(application, '退款规则是什么？')

        self.assertEqual(result['mode'], 'bailian')
        self.assertEqual(result['chunks'][0]['documentId'], document.id)
        self.assertIn('七天内可以申请退款', context)
        self.assertEqual(retrieve_mock.call_count, 2)
        local_index_mock.assert_not_called()
        local_embedding_mock.assert_not_called()

    def test_retrieve_maps_bailian_doc_id_metadata(self):
        document = self.create_document('expression-muscles.pdf')
        document.index_status = KnowledgeDocument.IndexStatus.READY
        document.bailian_file_id = 'file-expression'
        document.save(update_fields=['index_status', 'bailian_file_id', 'updated_at'])
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='百炼文档 ID 映射测试',
        )
        application.knowledge_bases.add(self.knowledge_base)

        with patch(
            'apps.ai_models.services.agent_knowledge.bailian.retrieve',
            return_value=[bailian.RetrievalNode(
                text='七种基本表情肌肉内容',
                score=0.91,
                metadata={'doc_id': 'file-expression'},
            )],
        ):
            result = retrieve_knowledge_chunks(query='表情肌肉', application=application)

        self.assertEqual(result['mode'], 'bailian')
        self.assertEqual(result['chunks'][0]['documentId'], document.id)

    def test_retrieve_never_accepts_remote_ids_outside_local_tenant_mapping(self):
        document = self.create_document('allowed.pdf')
        document.index_status = KnowledgeDocument.IndexStatus.READY
        document.bailian_file_id = 'allowed-file'
        document.save(update_fields=['index_status', 'bailian_file_id', 'updated_at'])
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='隔离测试智能体',
        )
        application.knowledge_bases.add(self.knowledge_base)

        with patch(
            'apps.ai_models.services.agent_knowledge.bailian.retrieve',
            return_value=[bailian.RetrievalNode(text='其他公司内容', score=0.99, metadata={'file_id': 'foreign-file'})],
        ):
            result = retrieve_knowledge_chunks(query='查询政策', application=application)

        self.assertEqual(result['chunks'], [])
