from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.ai_models.models import (
    AgentAnnotation,
    AgentAnnotationEmbedding,
    AgentApplication,
    EmbeddingModel,
    TenantKnowledgeModelSettings,
)
from apps.ai_models.services.annotation_embeddings import (
    EmbedQueryTimeout,
    model_fingerprint,
    question_hash,
    reindex_annotation_embeddings,
    sync_annotation_embedding,
    upsert_annotation_embedding,
)
from apps.ai_models.services.annotations import (
    AnnotationMatchPolicy,
    find_matching_annotation,
    find_matching_published_annotation,
    match_annotation,
    normalize_annotation_question,
)
from apps.ai_models.services.reply_blocks import build_published_annotation_snapshot
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


def _unit(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class AgentAnnotationSemanticMatchTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='annotation-semantic-tester', password='test123456')
        self.setup_tenant(self.user)
        self.application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='语义标注智能体',
            annotation_semantic_enabled=True,
            annotation_cosine_threshold=0.88,
        )
        self.embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='测试嵌入',
            api_key='dashscope-secret',
            base_url='https://example.test/embeddings',
            model='text-embedding-v4',
            dimensions=3,
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=self.embedding_model,
            is_active=True,
        )
        self.annotation = AgentAnnotation.objects.create(
            tenant=self.tenant,
            application=self.application,
            question='介绍一下你们公司',
            answer='我们是某某科技公司。',
            is_active=True,
            created_by=self.user,
        )
        self.fingerprint = model_fingerprint(self.embedding_model)
        self.company_vector = _unit([1.0, 0.0, 0.0])
        AgentAnnotationEmbedding.objects.create(
            annotation=self.annotation,
            tenant=self.tenant,
            application=self.application,
            embedding_fingerprint=self.fingerprint,
            embedding_model_name=self.embedding_model.model,
            dimensions=3,
            question_hash=question_hash(normalize_annotation_question(self.annotation.question)),
            embedding=self.company_vector,
            status=AgentAnnotationEmbedding.STATUS_READY,
            embedded_at=timezone.now(),
        )

    def _queryset(self):
        return AgentAnnotation.objects.filter(application=self.application, tenant=self.tenant)

    def test_exact_match_still_works(self):
        matched = find_matching_annotation(
            self._queryset(),
            '介绍一下你们公司。',
            application=self.application,
            tenant=self.tenant,
        )
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, self.annotation.id)

        result = match_annotation(
            question_text='介绍一下你们公司。',
            annotations=self._queryset(),
            tenant=self.tenant,
            application=self.application,
            source='live',
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.match_type, 'exact')
        self.assertEqual(result.score, 1.0)

    def test_semantic_match_above_threshold(self):
        query_vector = _unit([0.95, 0.05, 0.0])
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=query_vector,
        ) as embed_mock:
            result = match_annotation(
                question_text='你好，请给我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.match_type, 'semantic')
        self.assertEqual(result.annotation.id, self.annotation.id)
        self.assertGreaterEqual(result.score, 0.88)
        self.assertEqual(result.fingerprint, self.fingerprint)
        embed_mock.assert_called_once()

    def test_semantic_below_threshold_misses(self):
        product_vector = _unit([0.0, 1.0, 0.0])
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=product_vector,
        ):
            result = match_annotation(
                question_text='介绍一下你们产品',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)

    def test_embed_failure_degrades_to_none(self):
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            side_effect=EmbedQueryTimeout('timeout'),
        ):
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)

    def test_global_kill_switch_disables_semantic(self):
        with override_settings(ANNOTATION_SEMANTIC_MATCH_ENABLED=False), patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
        ) as embed_mock:
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)
        embed_mock.assert_not_called()

    def test_dim_mismatch_is_skipped(self):
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=[1.0, 0.0],
        ):
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)

    def test_fingerprint_isolation_ignores_other_buckets(self):
        other_fp = 'other|text-embedding-v3|3'
        AgentAnnotationEmbedding.objects.create(
            annotation=self.annotation,
            tenant=self.tenant,
            application=self.application,
            embedding_fingerprint=other_fp,
            embedding_model_name='text-embedding-v3',
            dimensions=3,
            question_hash=question_hash(normalize_annotation_question(self.annotation.question)),
            embedding=_unit([0.0, 1.0, 0.0]),
            status=AgentAnnotationEmbedding.STATUS_READY,
            embedded_at=timezone.now(),
        )
        # Query is orthogonal to current fingerprint vectors, so must miss even if other bucket is close.
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.0, 1.0, 0.0]),
        ):
            result = match_annotation(
                question_text='随便问一句',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)

    def test_dual_bucket_fallback_to_old_fingerprint(self):
        old_model = EmbeddingModel.objects.create(
            code='legacy',
            name='旧嵌入',
            api_key='legacy-key',
            base_url='https://example.test/legacy-embeddings',
            model='text-embedding-v3',
            dimensions=3,
            is_active=True,
        )
        old_fp = model_fingerprint(old_model)
        AgentAnnotationEmbedding.objects.filter(annotation=self.annotation, embedding_fingerprint=self.fingerprint).delete()
        AgentAnnotationEmbedding.objects.create(
            annotation=self.annotation,
            tenant=self.tenant,
            application=self.application,
            embedding_fingerprint=old_fp,
            embedding_model_name=old_model.model,
            dimensions=3,
            question_hash=question_hash(normalize_annotation_question(self.annotation.question)),
            embedding=self.company_vector,
            status=AgentAnnotationEmbedding.STATUS_READY,
            embedded_at=timezone.now(),
        )

        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.99, 0.01, 0.0]),
        ) as embed_mock:
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.match_type, 'semantic')
        self.assertEqual(result.fingerprint, old_fp)
        # embed_query is called with the fallback model
        self.assertEqual(embed_mock.call_args.args[0].id, old_model.id)

    def test_publish_snapshot_includes_ready_embedding(self):
        snapshot = build_published_annotation_snapshot(self.application)
        self.assertEqual(len(snapshot), 1)
        embedding = snapshot[0]['embedding']
        self.assertIsNotNone(embedding)
        self.assertEqual(embedding['fingerprint'], self.fingerprint)
        self.assertEqual(embedding['vector'], self.company_vector)
        self.assertEqual(embedding['model'], 'text-embedding-v4')

        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.97, 0.03, 0.0]),
        ):
            published = find_matching_published_annotation(
                snapshot,
                '你好请介绍一下你们公司',
                application=self.application,
                tenant=self.tenant,
            )
        self.assertIsNotNone(published)
        self.assertEqual(published['id'], self.annotation.id)
        self.assertEqual(published['answer'], '我们是某某科技公司。')

    def test_question_change_invalidates_old_vectors(self):
        self.annotation.question = '公司地址在哪里'
        self.annotation.save(update_fields=['question', 'updated_at'])
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.0, 0.0, 1.0]),
        ):
            record = sync_annotation_embedding(self.annotation, question_changed=True)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, AgentAnnotationEmbedding.STATUS_READY)
        self.assertEqual(
            AgentAnnotationEmbedding.objects.filter(annotation=self.annotation).count(),
            1,
        )
        self.assertEqual(
            AgentAnnotationEmbedding.objects.get(annotation=self.annotation).question_hash,
            question_hash(normalize_annotation_question('公司地址在哪里')),
        )

    def test_upsert_marks_failed_on_embed_error(self):
        AgentAnnotationEmbedding.objects.filter(annotation=self.annotation).delete()
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            side_effect=EmbedQueryTimeout('timeout'),
        ):
            record = upsert_annotation_embedding(self.annotation, model=self.embedding_model)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, AgentAnnotationEmbedding.STATUS_FAILED)

    def test_reindex_command_path_counts(self):
        AgentAnnotationEmbedding.objects.filter(annotation=self.annotation).delete()
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=self.company_vector,
        ):
            stats = reindex_annotation_embeddings(tenant=self.tenant, force=True)
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['ready'], 1)
        self.assertEqual(stats['failed'], 0)

    def test_tenant_isolation(self):
        other_user = User.objects.create_user(username='other-semantic', password='test123456')
        from apps.tenants.models import Tenant

        other_tenant = Tenant.objects.create(code='other-semantic', name='其他公司')
        other_app = AgentApplication.objects.create(
            tenant=other_tenant,
            created_by=other_user,
            name='其他智能体',
        )
        other_annotation = AgentAnnotation.objects.create(
            tenant=other_tenant,
            application=other_app,
            question='介绍一下你们公司',
            answer='别人的答案',
            is_active=True,
        )
        AgentAnnotationEmbedding.objects.create(
            annotation=other_annotation,
            tenant=other_tenant,
            application=other_app,
            embedding_fingerprint=self.fingerprint,
            embedding_model_name=self.embedding_model.model,
            dimensions=3,
            question_hash=question_hash(normalize_annotation_question(other_annotation.question)),
            embedding=self.company_vector,
            status=AgentAnnotationEmbedding.STATUS_READY,
            embedded_at=timezone.now(),
        )

        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.99, 0.01, 0.0]),
        ):
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.annotation.id, self.annotation.id)
        self.assertNotEqual(result.annotation.id, other_annotation.id)


    def test_policy_disable_on_application(self):
        self.application.annotation_semantic_enabled = False
        self.application.save(update_fields=['annotation_semantic_enabled', 'updated_at'])
        with patch('apps.ai_models.services.annotation_embeddings.embed_query') as embed_mock:
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                source='live',
            )
        self.assertIsNone(result)
        embed_mock.assert_not_called()

    def test_custom_threshold_policy(self):
        policy = AnnotationMatchPolicy(semantic_enabled=True, cosine_threshold=0.999)
        with patch(
            'apps.ai_models.services.annotation_embeddings.embed_query',
            return_value=_unit([0.9, 0.1, 0.0]),
        ):
            result = match_annotation(
                question_text='帮我介绍一下你们公司',
                annotations=self._queryset(),
                tenant=self.tenant,
                application=self.application,
                policy=policy,
                source='live',
            )
        self.assertIsNone(result)
