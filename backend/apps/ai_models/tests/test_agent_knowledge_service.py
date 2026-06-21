from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from unittest.mock import patch

from apps.ai_models.models import AgentApplication, EmbeddingModel, RerankModel
from apps.ai_models.services.agent_knowledge import retrieve_knowledge_context
from apps.knowledge_base.models import KnowledgeDocument, KnowledgeDocumentChunk
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class _DummyDashScopeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class _DummyDashScopeClient:
    def __init__(self, *args, **kwargs):
        self.post_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, json=None, headers=None):
        self.post_calls.append({'url': url, 'json': json, 'headers': headers or {}})
        if url.endswith('/embeddings'):
            texts = _normalize_embedding_inputs(json)
            return _DummyDashScopeResponse(
                {
                    'data': [
                        {'index': index, 'embedding': _vector_for_text(text)}
                        for index, text in enumerate(texts)
                    ]
                }
            )
        if url.endswith('/text-rerank'):
            documents = list((json.get('input') or {}).get('documents') or [])
            ranked_indexes = sorted(
                range(len(documents)),
                key=lambda index: 0 if '退款' in documents[index] else 1,
            )
            return _DummyDashScopeResponse(
                {
                    'output': {
                        'results': [
                            {'index': index, 'relevance_score': 0.99 if '退款' in documents[index] else 0.12}
                            for index in ranked_indexes
                        ]
                    }
                }
            )
        raise AssertionError(f'Unexpected URL: {url}')


class _DocumentEmbeddingFailureClient(_DummyDashScopeClient):
    def post(self, url, *, json=None, headers=None):
        self.post_calls.append({'url': url, 'json': json, 'headers': headers or {}})
        if url.endswith('/embeddings'):
            texts = _normalize_embedding_inputs(json)
            if any('客户购买后七天内可以申请退款' in text for text in texts):
                return _DummyDashScopeResponse({'message': 'temporary embedding failure'}, status_code=500)
            return _DummyDashScopeResponse(
                {
                    'data': [
                        {'index': index, 'embedding': _vector_for_text(text)}
                        for index, text in enumerate(texts)
                    ]
                }
            )
        raise AssertionError(f'Unexpected URL: {url}')


def _normalize_embedding_inputs(payload: dict | None) -> list[str]:
    inputs = (payload or {}).get('input')
    if isinstance(inputs, str):
        return [inputs]
    return list(inputs or [])


def _vector_for_text(text: str) -> list[float]:
    if '退款' in text:
        return [1.0, 0.0, 0.0]
    if '营业' in text:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]


class AgentKnowledgeRetrievalTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kb-rag-tester', password='test123456')
        self.setup_tenant(self.user)
        self.application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='售后 Agent Application',
        )

    def create_document(self, *, title: str, body: str) -> KnowledgeDocument:
        return KnowledgeDocument.objects.create(
            tenant=self.tenant,
            title=title,
            file=ContentFile(body.encode('utf-8'), name=f'{title}.md'),
            processing_status=KnowledgeDocument.STATUS_APPROVED,
        )

    def test_retrieve_knowledge_context_uses_embedding_and_rerank_models(self):
        refund_document = self.create_document(
            title='退款政策',
            body='退款政策\n客户购买后七天内可以申请退款，到账时间通常为三个工作日。',
        )
        opening_hours_document = self.create_document(
            title='营业时间',
            body='营业时间\n门店工作日 09:00 到 18:00 提供服务。',
        )
        self.application.knowledge_documents.add(refund_document, opening_hours_document)
        EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        RerankModel.objects.create(
            code='aliyun',
            name='阿里云文本重排序',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
            model='qwen3-vl-rerank',
            is_active=True,
        )
        dummy_client = _DummyDashScopeClient()

        with patch('apps.ai_models.services.agent_knowledge.httpx.Client', return_value=dummy_client):
            context = retrieve_knowledge_context(self.application, '退款多久到账？', top_n=2, max_chars=2000)

        self.assertIn('【知识库参考信息】', context)
        self.assertIn('文档: 退款政策', context)
        self.assertIn('三个工作日', context)
        if '文档: 营业时间' in context:
            self.assertLess(context.index('文档: 退款政策'), context.index('文档: 营业时间'))
        self.assertTrue(KnowledgeDocumentChunk.objects.filter(document=refund_document).exists())
        self.assertTrue(KnowledgeDocumentChunk.objects.filter(document=opening_hours_document).exists())
        self.assertTrue(any(call['url'].endswith('/embeddings') for call in dummy_client.post_calls))
        self.assertTrue(any(call['url'].endswith('/text-rerank') for call in dummy_client.post_calls))
        self.assertTrue(
            all(call['headers'].get('Authorization') == 'Bearer dashscope-secret' for call in dummy_client.post_calls)
        )

    def test_retrieve_knowledge_context_preserves_stale_chunks_when_refresh_fails(self):
        refund_document = self.create_document(
            title='退款政策',
            body='退款政策\n客户购买后七天内可以申请退款，到账时间通常为三个工作日。',
        )
        self.application.knowledge_documents.add(refund_document)
        EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        stale_chunk = KnowledgeDocumentChunk.objects.create(
            document=refund_document,
            tenant=self.tenant,
            chunk_index=0,
            content='旧缓存：退款需要十个工作日。',
            content_hash='stale-cache',
            embedding=[1.0, 0.0, 0.0],
            embedding_model='text-embedding-v4',
        )
        dummy_client = _DocumentEmbeddingFailureClient()

        with patch('apps.ai_models.services.agent_knowledge.httpx.Client', return_value=dummy_client):
            context = retrieve_knowledge_context(self.application, '退款多久到账？', top_n=2, max_chars=2000)

        self.assertIn('三个工作日', context)
        self.assertNotIn('十个工作日', context)
        stale_chunk.refresh_from_db()
        self.assertEqual(stale_chunk.content, '旧缓存：退款需要十个工作日。')


class ModelConfigDefaultsTests(TestCase):
    @override_settings(
        ALIYUN_EMBEDDING_API_KEY='env-embedding-key',
        ALIYUN_EMBEDDING_BASE_URL='https://example.com/embeddings',
        ALIYUN_EMBEDDING_MODEL='text-embedding-v4',
        ALIYUN_EMBEDDING_DIMENSIONS=1024,
        ALIYUN_RERANK_API_KEY='env-rerank-key',
        ALIYUN_RERANK_BASE_URL='https://example.com/text-rerank',
        ALIYUN_RERANK_MODEL='qwen3-vl-rerank',
    )
    def test_load_aliyun_backfills_blank_model_config_from_settings(self):
        EmbeddingModel.objects.create(code='aliyun', name='阿里云文本嵌入', base_url='', model='')
        RerankModel.objects.create(code='aliyun', name='阿里云文本重排序', base_url='', model='')

        embedding_model = EmbeddingModel.load_aliyun()
        rerank_model = RerankModel.load_aliyun()

        self.assertEqual(embedding_model.api_key, 'env-embedding-key')
        self.assertEqual(embedding_model.base_url, 'https://example.com/embeddings')
        self.assertEqual(embedding_model.model, 'text-embedding-v4')
        self.assertEqual(embedding_model.dimensions, 1024)
        self.assertEqual(rerank_model.api_key, 'env-rerank-key')
        self.assertEqual(rerank_model.base_url, 'https://example.com/text-rerank')
        self.assertEqual(rerank_model.model, 'qwen3-vl-rerank')

