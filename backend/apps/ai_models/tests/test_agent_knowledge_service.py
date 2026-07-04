from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from unittest.mock import patch

import httpx

from apps.ai_models.models import AgentApplication, EmbeddingModel, RerankModel, TenantKnowledgeModelSettings
from apps.ai_models.services.agent_knowledge import (
    media_blocks_for_reply_text,
    retrieve_knowledge_chunks,
    retrieve_knowledge_context,
)
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk, KnowledgeMediaAsset
from apps.resources.models import Resource
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
        embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        rerank_model = RerankModel.objects.create(
            code='aliyun',
            name='阿里云文本重排序',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
            model='qwen3-vl-rerank',
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=embedding_model,
            rerank_model=rerank_model,
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
        embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=embedding_model,
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

    def test_retrieve_knowledge_chunks_filters_low_confidence_vector_hits_before_media_matching(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='低置信知识库',
            retrieval_min_score=0.5,
            created_by=self.user,
        )
        document = self.create_document(
            title='退款政策',
            body='退款政策\n客户购买后七天内可以申请退款，到账时间通常为三个工作日。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        KnowledgeDocumentChunk.objects.create(
            document=document,
            tenant=self.tenant,
            chunk_index=0,
            content='退款政策\n客户购买后七天内可以申请退款。',
            content_hash='low-confidence',
            embedding=[0.1, 0.0, 0.995],
            embedding_model='text-embedding-v4',
        )
        guide_image = Resource.objects.create(
            tenant=self.tenant,
            name='退款流程图',
            resource_type=Resource.TYPE_IMAGE,
            description='退款政策流程图片',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=guide_image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='退款流程图',
            keywords='退款 政策 流程',
            description='退款政策说明图',
        )
        embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=embedding_model,
            is_active=True,
        )

        with (
            patch('apps.ai_models.services.agent_knowledge.build_document_index', return_value={'status': KnowledgeDocument.IndexStatus.READY}),
            patch('apps.ai_models.services.agent_knowledge._embed_texts', return_value=[[1.0, 0.0, 0.0]]),
        ):
            result = retrieve_knowledge_chunks(query='退款多久到账？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'vector')
        self.assertEqual(result['chunks'], [])
        self.assertEqual(result['mediaAssets'], [])

    def test_transport_error_falls_back_to_keyword_without_error_log(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='外部模型网络异常知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='退款政策',
            body='退款政策\n客户购买后七天内可以申请退款，到账时间通常为三个工作日。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=embedding_model,
            is_active=True,
        )

        with (
            patch('apps.ai_models.services.agent_knowledge.build_document_index', return_value={'status': KnowledgeDocument.IndexStatus.READY}),
            patch('apps.ai_models.services.agent_knowledge._embed_texts', side_effect=httpx.ConnectError('[SSL: UNEXPECTED_EOF_WHILE_READING] EOF')),
            patch('apps.ai_models.services.agent_knowledge.logger.exception') as log_exception,
            self.assertLogs('apps.ai_models.services.agent_knowledge', level='WARNING') as captured_logs,
        ):
            result = retrieve_knowledge_chunks(query='退款多久到账？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'keyword')
        self.assertIn('三个工作日', result['chunks'][0]['content'])
        self.assertTrue(any('External model transport error during vector knowledge chunk retrieval' in log for log in captured_logs.output))
        log_exception.assert_not_called()

    def test_low_information_query_skips_knowledge_and_media_retrieval(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='问候测试知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='退款政策',
            body='退款政策\n客户购买后七天内可以申请退款。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        image = Resource.objects.create(
            tenant=self.tenant,
            name='退款流程图',
            resource_type=Resource.TYPE_IMAGE,
            description='退款流程说明图',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='退款流程图',
            keywords='退款 流程',
            description='退款流程图片',
        )

        result = retrieve_knowledge_chunks(query='你好啊', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'skipped')
        self.assertTrue(result['retrievalSkipped'])
        self.assertEqual(result['skipReason'], 'low_information_query')
        self.assertEqual(result['chunks'], [])
        self.assertEqual(result['mediaAssets'], [])

    def test_media_relevance_is_normalized_for_keyword_retrieval(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='素材分数知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='退款流程',
            body='退款流程\n客户申请退款后，客服会审核订单并确认到账时间。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        image = Resource.objects.create(
            tenant=self.tenant,
            name='退款流程图',
            resource_type=Resource.TYPE_IMAGE,
            description='退款流程说明图',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='退款流程图',
            keywords='退款 流程 审核 到账',
            description='退款流程、审核订单、到账时间说明图',
            priority=10,
        )

        result = retrieve_knowledge_chunks(query='退款流程是什么？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'keyword')
        self.assertEqual(len(result['mediaAssets']), 1)
        self.assertGreaterEqual(result['mediaAssets'][0]['relevance'], 0.3)
        self.assertLessEqual(result['mediaAssets'][0]['relevance'], 1.0)

    def test_reply_text_keywords_are_used_for_media_matching_after_text_recall(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='大唐不夜城知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='大唐不夜城美食推荐',
            body='大唐不夜城周边适合做美食推荐，包含本地小吃、甜品和夜游路线。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        steamed_cake_image = Resource.objects.create(
            tenant=self.tenant,
            name='甑糕图片',
            resource_type=Resource.TYPE_IMAGE,
            description='甑糕美食图片',
        )
        roujiamo_image = Resource.objects.create(
            tenant=self.tenant,
            name='肉夹馍图片',
            resource_type=Resource.TYPE_IMAGE,
            description='肉夹馍美食图片',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=steamed_cake_image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='甑糕图片',
            keywords='甑糕 甜品 软糯',
            description='大唐不夜城附近甑糕小吃图片',
        )
        KnowledgeMediaAsset.objects.create(
            tenant=self.tenant,
            knowledge_base=knowledge_base,
            resource=roujiamo_image,
            resource_type=Resource.TYPE_IMAGE,
            resource_name='肉夹馍图片',
            keywords='肉夹馍 小吃 酥香',
            description='大唐不夜城附近肉夹馍小吃图片',
        )

        recall_result = retrieve_knowledge_chunks(
            query='大唐不夜城有什么美食推荐？',
            knowledge_base=knowledge_base,
            top_n=3,
            include_media=False,
        )
        blocks = media_blocks_for_reply_text(
            recall_result=recall_result,
            user_query='大唐不夜城有什么美食推荐？',
            reply_text='可以试试甑糕，口感软糯；也可以吃肉夹馍，酥香管饱，适合夜游时作为小吃。',
            tenant=self.tenant,
        )

        self.assertEqual(recall_result['mediaAssets'], [])
        self.assertEqual(
            blocks,
            [
                {'type': 'image', 'resourceId': roujiamo_image.id},
                {'type': 'image', 'resourceId': steamed_cake_image.id},
            ],
        )

    def test_collection_food_query_returns_multiple_related_media_assets(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='大唐不夜城素材知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='大唐不夜城美食指南',
            body='大唐不夜城适合做美食推荐，附近有烧烤、肉夹馍、甑糕、汤品和夜游小吃。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        resources = [
            Resource.objects.create(tenant=self.tenant, name=name, resource_type=Resource.TYPE_IMAGE, description=f'{name}图片')
            for name in ['烧烤图片', '肉夹馍图片', '甑糕图片', '汤品图片']
        ]
        for resource in resources:
            KnowledgeMediaAsset.objects.create(
                tenant=self.tenant,
                knowledge_base=knowledge_base,
                resource=resource,
                resource_type=Resource.TYPE_IMAGE,
                resource_name=resource.name,
                keywords=f'{resource.name} 大唐不夜城 美食 小吃',
                description=f'大唐不夜城附近的{resource.name}，适合回答美食推荐问题',
            )

        result = retrieve_knowledge_chunks(query='大唐不夜城的美食有什么？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'keyword')
        self.assertGreaterEqual(len(result['mediaAssets']), 4)

        blocks = media_blocks_for_reply_text(
            recall_result=result,
            user_query='大唐不夜城的美食有什么？',
            reply_text='可以先看看烧烤，适合夜游时吃。',
            tenant=self.tenant,
        )
        self.assertGreaterEqual(len(blocks), 4)

    def test_media_recall_respects_knowledge_base_configured_limit(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='素材上限知识库',
            media_max_assets=2,
            media_min_relevance=0.1,
            created_by=self.user,
        )
        document = self.create_document(
            title='美食指南',
            body='大唐不夜城适合推荐烧烤、肉夹馍、甑糕和汤品。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        for name in ['烧烤图片', '肉夹馍图片', '甑糕图片', '汤品图片']:
            resource = Resource.objects.create(tenant=self.tenant, name=name, resource_type=Resource.TYPE_IMAGE)
            KnowledgeMediaAsset.objects.create(
                tenant=self.tenant,
                knowledge_base=knowledge_base,
                resource=resource,
                resource_type=Resource.TYPE_IMAGE,
                resource_name=name,
                keywords=f'{name} 大唐不夜城 美食 小吃',
            )

        result = retrieve_knowledge_chunks(query='大唐不夜城的美食有什么？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(len(result['mediaAssets']), 2)

    def test_multimodal_vector_query_keeps_multiple_text_relevant_food_media_assets(self):
        knowledge_base = KnowledgeBase.objects.create(
            tenant=self.tenant,
            name='大唐不夜城多模态素材知识库',
            created_by=self.user,
        )
        document = self.create_document(
            title='大唐不夜城美食指南',
            body='大唐不夜城附近有多种美食，适合推荐烧烤、水盆、肉夹馍和夜市小吃。',
        )
        document.knowledge_base = knowledge_base
        document.save(update_fields=['knowledge_base'])
        KnowledgeDocumentChunk.objects.create(
            document=document,
            tenant=self.tenant,
            chunk_index=0,
            content='大唐不夜城附近有多种美食，适合推荐烧烤、水盆、肉夹馍和夜市小吃。',
            content_hash='datang-food',
            embedding=[1.0, 0.0, 0.0],
            embedding_model='text-embedding-v4',
        )
        embedding_model = EmbeddingModel.objects.create(
            code='aliyun',
            name='阿里云通用文本向量',
            api_key='dashscope-secret',
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            model='text-embedding-v4',
            is_active=True,
        )
        TenantKnowledgeModelSettings.objects.create(
            tenant=self.tenant,
            embedding_model=embedding_model,
            is_active=True,
        )
        assets = []
        for index, (name, description, media_embedding) in enumerate([
            ('清真刚刚烤肉', '大唐不夜城附近的美食餐厅，画面包含烧烤、炒菜、面食和排队顾客。', [0.99, 0.01, 0.0]),
            ('学斌水盆', '大唐不夜城店的美食和店面，包含汤品、红烧肉、辣椒和配菜。', [0.1, 0.9, 0.0]),
            ('肉夹馍小吃', '大唐不夜城附近夜游小吃，适合回答美食有什么。', [0.1, 0.0, 0.9]),
        ]):
            resource = Resource.objects.create(
                tenant=self.tenant,
                name=name,
                resource_type=Resource.TYPE_IMAGE,
                description=f'{name}图片',
            )
            assets.append(
                KnowledgeMediaAsset.objects.create(
                    tenant=self.tenant,
                    knowledge_base=knowledge_base,
                    resource=resource,
                    resource_type=Resource.TYPE_IMAGE,
                    resource_name=name,
                    keywords='',
                    description='',
                    vlm_description=description,
                    multimodal_embedding=media_embedding,
                    embedding_status=KnowledgeMediaAsset.EmbeddingStatus.READY,
                    priority=index,
                )
            )

        with (
            patch('apps.ai_models.services.agent_knowledge.build_document_index', return_value={'status': KnowledgeDocument.IndexStatus.READY}),
            patch('apps.ai_models.services.agent_knowledge._embed_texts', return_value=[[1.0, 0.0, 0.0]]),
            patch('apps.knowledge_base.media_indexing.embed_media_query', return_value=[1.0, 0.0, 0.0]),
        ):
            result = retrieve_knowledge_chunks(query='大唐不夜城的美食有什么？', knowledge_base=knowledge_base, top_n=3)

        self.assertEqual(result['mode'], 'vector')
        self.assertGreaterEqual(len(result['mediaAssets']), 3)
        self.assertEqual(
            {item['resourceName'] for item in result['mediaAssets']},
            {asset.resource_name for asset in assets},
        )


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
