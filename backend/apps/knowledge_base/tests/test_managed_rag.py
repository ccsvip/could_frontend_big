from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.ai_models.models import AgentApplication, BailianKnowledgeConfig, TenantKnowledgeModelSettings
from apps.ai_models.services.agent_knowledge import retrieve_knowledge_chunks, retrieve_knowledge_context
from apps.knowledge_base import bailian
from apps.knowledge_base.managed_indexing import _remote_index_name, build_managed_document_index
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument
from apps.knowledge_base.tenant_provisioning import ensure_tenant_category, tenant_category_name
from apps.tenants.models import Tenant
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

    def test_bailian_create_index_rejects_invalid_name_before_remote_request(self):
        for invalid_name in ('', '   ', 'x' * 21):
            with (
                self.subTest(name=invalid_name),
                patch('apps.knowledge_base.bailian._client') as client_factory,
                self.assertRaisesMessage(bailian.BailianKnowledgeError, '百炼索引名称长度必须为 1 到 20 个字符'),
            ):
                bailian.create_index(name=invalid_name, file_id='file-1')

            client_factory.assert_not_called()

    def test_remote_index_name_is_stable_unique_and_within_bailian_limit(self):
        first = KnowledgeBase(pk=1)
        second = KnowledgeBase(pk=2)
        largest = KnowledgeBase(pk=2**63 - 1)

        self.assertEqual(_remote_index_name(first), _remote_index_name(first))
        self.assertNotEqual(_remote_index_name(first), _remote_index_name(second))
        self.assertEqual(len(_remote_index_name(largest)), 20)
        self.assertRegex(_remote_index_name(largest), r'^solin-k[0-9a-z]+$')

    def test_official_document_formats_use_managed_indexing(self):
        for suffix in ('pdf', 'docx', 'xlsx'):
            with self.subTest(suffix=suffix):
                document = self.create_document(f'document-{suffix}.{suffix}')
                with (
                    patch('apps.knowledge_base.managed_indexing.ensure_tenant_category', return_value='category-tenant'),
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
                apply_lease.assert_called_once_with(
                    category_id='category-tenant',
                    file_name=f'document-{suffix}.{suffix}',
                    content_md5=document.content_md5,
                    file_size=document.file_size,
                )

    def test_long_knowledge_base_name_uses_valid_remote_index_name(self):
        self.knowledge_base.name = '这是一个远远超过百炼索引名称长度限制的知识库名称'
        self.knowledge_base.bailian_index_id = ''
        self.knowledge_base.save(update_fields=['name', 'bailian_index_id', 'updated_at'])
        document = self.create_document('long-name.pdf')

        with (
            patch('apps.knowledge_base.managed_indexing.ensure_tenant_category', return_value='category-tenant'),
            patch('apps.knowledge_base.managed_indexing.bailian.apply_upload_lease') as apply_lease,
            patch('apps.knowledge_base.managed_indexing.bailian.upload_file'),
            patch('apps.knowledge_base.managed_indexing.bailian.add_file', return_value='file-long-name'),
            patch(
                'apps.knowledge_base.managed_indexing.bailian.describe_file',
                return_value={'status': 'PARSE_SUCCESS', 'error': '', 'parser': 'AUTO_SELECT'},
            ),
            patch('apps.knowledge_base.managed_indexing.bailian.create_index', return_value='index-long-name') as create_index,
            patch('apps.knowledge_base.managed_indexing.bailian.submit_index', return_value='job-long-name'),
            patch('apps.knowledge_base.managed_indexing.bailian.get_index_job_status', return_value='COMPLETED'),
        ):
            apply_lease.return_value = bailian.UploadLease('lease-1', 'https://upload.invalid', 'PUT', {})
            result = build_managed_document_index(document.id)

        remote_name = create_index.call_args.kwargs['name']
        self.assertEqual(result['status'], KnowledgeDocument.IndexStatus.READY)
        self.assertLessEqual(len(remote_name), 20)
        self.assertRegex(remote_name, r'^solin-k[0-9a-z]+$')

    def test_tenant_category_is_created_once_and_reused(self):
        BailianKnowledgeConfig.objects.update_or_create(
            pk=1,
            defaults={
                'access_key_id': 'access-key-id',
                'access_key_secret_encrypted': 'encrypted-secret',
                'workspace_id': 'workspace-1',
                'is_active': True,
            },
        )
        with (
            patch('apps.knowledge_base.tenant_provisioning.bailian.find_category_by_name', return_value='') as find_mock,
            patch('apps.knowledge_base.tenant_provisioning.bailian.create_category', return_value='category-tenant') as create_mock,
        ):
            first = ensure_tenant_category(self.tenant.id)
            second = ensure_tenant_category(self.tenant.id)

        self.assertEqual(first, 'category-tenant')
        self.assertEqual(second, 'category-tenant')
        find_mock.assert_called_once_with(tenant_category_name(self.tenant.id))
        create_mock.assert_called_once_with(tenant_category_name(self.tenant.id))
        tenant_settings = TenantKnowledgeModelSettings.objects.get(tenant=self.tenant)
        self.assertEqual(tenant_settings.bailian_category_id, 'category-tenant')
        self.assertEqual(tenant_settings.bailian_category_workspace_id, 'workspace-1')

    def test_tenant_category_recovers_existing_remote_mapping(self):
        BailianKnowledgeConfig.objects.update_or_create(
            pk=1,
            defaults={
                'access_key_id': 'access-key-id',
                'access_key_secret_encrypted': 'encrypted-secret',
                'workspace_id': 'workspace-1',
                'is_active': True,
            },
        )
        with (
            patch(
                'apps.knowledge_base.tenant_provisioning.bailian.find_category_by_name',
                return_value='existing-category',
            ),
            patch('apps.knowledge_base.tenant_provisioning.bailian.create_category') as create_mock,
        ):
            category_id = ensure_tenant_category(self.tenant.id)

        self.assertEqual(category_id, 'existing-category')
        create_mock.assert_not_called()

    def test_different_tenants_receive_different_categories(self):
        BailianKnowledgeConfig.objects.update_or_create(
            pk=1,
            defaults={
                'access_key_id': 'access-key-id',
                'access_key_secret_encrypted': 'encrypted-secret',
                'workspace_id': 'workspace-1',
                'is_active': True,
            },
        )
        other_tenant = Tenant.objects.create(name='另一家公司', code='other-tenant')
        TenantKnowledgeModelSettings.objects.create(
            tenant=other_tenant,
            managed_rag_enabled=True,
            is_active=True,
        )
        category_ids = {
            tenant_category_name(self.tenant.id): 'category-first',
            tenant_category_name(other_tenant.id): 'category-second',
        }

        with (
            patch('apps.knowledge_base.tenant_provisioning.bailian.find_category_by_name', return_value=''),
            patch(
                'apps.knowledge_base.tenant_provisioning.bailian.create_category',
                side_effect=lambda name: category_ids[name],
            ),
        ):
            first = ensure_tenant_category(self.tenant.id)
            second = ensure_tenant_category(other_tenant.id)

        self.assertEqual(first, 'category-first')
        self.assertEqual(second, 'category-second')

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
