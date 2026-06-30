from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

from django.db.models import Count, F, Q
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from kombu.exceptions import OperationalError
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import (
    CanBulkDownloadKnowledgeBase,
    CanDownloadKnowledgeBase,
    CanUploadKnowledgeBase,
    CanViewKnowledgeBase,
)
from config.business_cache import CachedBusinessResponseMixin, clear_business_cache_namespace
from apps.resources.models import Resource
from apps.tenants.mixins import TenantScopedQuerysetMixin

from .models import KnowledgeBase, KnowledgeDocument, KnowledgeMediaAsset
from .serializers import (
    KnowledgeBaseSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeMediaAssetCreateSerializer,
    KnowledgeMediaAssetSerializer,
    KnowledgeRecallTestSerializer,
)
from .services import (
    notify_knowledge_bulk_download,
    notify_knowledge_document_deleted,
    notify_knowledge_document_event,
)
from .tasks import build_knowledge_document_index, build_knowledge_media_asset_index

MAX_BULK_DOWNLOAD_COUNT = 20
MAX_BULK_DOWNLOAD_SIZE = 200 * 1024 * 1024


def get_document_size(document: KnowledgeDocument) -> int:
    if document.file_size is not None:
        return document.file_size
    try:
        return document.file.size
    except OSError:
        return 0


class PermissionMappedViewSet(viewsets.GenericViewSet):
    permission_map: dict[str, list[type]] = {}

    def get_permissions(self):
        permission_classes = self.permission_map.get(self.action, self.permission_map.get('list', []))
        return [permission() for permission in permission_classes]


def build_zip_entry_name(file_name: str, existing_names: set[str]) -> str:
    candidate = file_name or 'document'
    stem = Path(candidate).stem or 'document'
    suffix = Path(candidate).suffix
    deduped_name = candidate
    index = 1
    while deduped_name in existing_names:
        deduped_name = f'{stem}({index}){suffix}'
        index += 1
    existing_names.add(deduped_name)
    return deduped_name


def build_content_disposition(filename: str) -> str:
    encoded = quote(filename)
    return f"attachment; filename*=UTF-8''{encoded}"


def enqueue_document_index(document: KnowledgeDocument, *, force: bool = False) -> dict:
    KnowledgeDocument.objects.filter(pk=document.pk).update(
        index_status=KnowledgeDocument.IndexStatus.PENDING,
        index_error='',
        indexed_at=None,
    )
    document.index_status = KnowledgeDocument.IndexStatus.PENDING
    document.index_error = ''
    document.indexed_at = None
    try:
        build_knowledge_document_index.delay(document.pk, force=force)
        return {'documentId': document.pk, 'queued': True}
    except (OperationalError, OSError):
        from apps.ai_models.services.agent_knowledge import build_document_index_by_id

        result = build_document_index_by_id(document.pk, force=force)
        document.refresh_from_db()
        return {'documentId': document.pk, 'queued': False, **result}


def enqueue_media_asset_index(asset: KnowledgeMediaAsset, *, force: bool = False) -> dict:
    KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
        embedding_status=KnowledgeMediaAsset.EmbeddingStatus.PENDING,
        embedding_error='',
        embedding_processed_at=None,
    )
    try:
        build_knowledge_media_asset_index.delay(asset.pk, force=force)
        return {'assetId': asset.pk, 'queued': True}
    except (OperationalError, OSError):
        from .media_indexing import build_media_asset_index

        return {'assetId': asset.pk, 'queued': False, **build_media_asset_index(asset.pk, force=force)}


@extend_schema_view(
    list=extend_schema(tags=['KnowledgeBase']),
    retrieve=extend_schema(tags=['KnowledgeBase']),
    create=extend_schema(tags=['KnowledgeBase']),
    update=extend_schema(tags=['KnowledgeBase']),
    partial_update=extend_schema(tags=['KnowledgeBase']),
    destroy=extend_schema(tags=['KnowledgeBase']),
    documents=extend_schema(tags=['KnowledgeBase']),
    recall_test=extend_schema(tags=['KnowledgeBase']),
    media_assets=extend_schema(tags=['KnowledgeBase']),
    media_asset_detail=extend_schema(tags=['KnowledgeBase']),
    index=extend_schema(tags=['KnowledgeBase']),
)
class KnowledgeBaseViewSet(
    CachedBusinessResponseMixin,
    TenantScopedQuerysetMixin,
    PermissionMappedViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = KnowledgeBaseSerializer
    queryset = KnowledgeBase.objects.select_related('created_by').order_by('-updated_at', '-id')
    business_cache_namespace = 'knowledge_base'
    permission_map = {
        'list': [CanViewKnowledgeBase],
        'retrieve': [CanViewKnowledgeBase],
        'create': [CanUploadKnowledgeBase],
        'update': [CanUploadKnowledgeBase],
        'partial_update': [CanUploadKnowledgeBase],
        'destroy': [CanUploadKnowledgeBase],
        'documents': [CanViewKnowledgeBase],
        'recall_test': [CanViewKnowledgeBase],
        'media_assets': [CanViewKnowledgeBase],
        'media_asset_detail': [CanViewKnowledgeBase],
        'index': [CanUploadKnowledgeBase],
    }
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == 'documents' and self.request.method == 'POST':
            return [CanUploadKnowledgeBase()]
        if self.action == 'media_assets' and self.request.method == 'POST':
            return [CanUploadKnowledgeBase()]
        if self.action == 'media_asset_detail' and self.request.method in {'PATCH', 'DELETE'}:
            return [CanUploadKnowledgeBase()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset().annotate(
            document_count=Count('documents', distinct=True),
        )
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = self.request_tenant
        return context

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_create_kwargs())
        self.clear_cached_business_responses()

    def perform_update(self, serializer):
        index_config_changed = any(
            field in serializer.validated_data
            for field in ('chunk_size', 'chunk_overlap')
        )
        instance = serializer.save()
        if index_config_changed:
            for document in instance.documents.filter(tenant=instance.tenant).order_by('id'):
                enqueue_document_index(document, force=True)
        self.clear_cached_business_responses()

    def perform_destroy(self, instance: KnowledgeBase):
        documents = list(instance.documents.all())
        super().perform_destroy(instance)
        for document in documents:
            if document.file:
                document.file.delete(save=False)
            document.delete()
        self.clear_cached_business_responses()

    @action(detail=True, methods=['get', 'post'], url_path='documents')
    def documents(self, request, pk=None):
        knowledge_base = self.get_object()
        if request.method == 'GET':
            queryset = knowledge_base.documents.select_related('uploaded_by', 'knowledge_base').order_by('-updated_at', '-id')
            keyword = request.query_params.get('keyword', '').strip()
            if keyword:
                queryset = queryset.filter(Q(title__icontains=keyword) | Q(file_name__icontains=keyword))
            serializer = KnowledgeDocumentSerializer(
                queryset,
                many=True,
                context={**self.get_serializer_context(), 'request': request},
            )
            return Response(serializer.data)

        serializer = KnowledgeDocumentSerializer(
            data=request.data,
            context={**self.get_serializer_context(), 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        document = serializer.save(
            uploaded_by=request.user,
            knowledge_base=knowledge_base,
            **self.tenant_create_kwargs(),
        )
        self.clear_cached_business_responses()
        notify_knowledge_document_event('create', getattr(self.request, 'user', None), document)
        enqueue_document_index(document)
        return Response(
            KnowledgeDocumentSerializer(
                document,
                context={**self.get_serializer_context(), 'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='recall-test')
    def recall_test(self, request, pk=None):
        knowledge_base = self.get_object()
        serializer = KnowledgeRecallTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.ai_models.services.agent_knowledge import retrieve_knowledge_chunks

        result = retrieve_knowledge_chunks(
            query=serializer.validated_data['query'],
            knowledge_base=knowledge_base,
            tenant=knowledge_base.tenant,
            top_n=serializer.validated_data.get('topN') or knowledge_base.retrieval_top_n,
        )
        return Response(result)

    @action(detail=True, methods=['get', 'post'], url_path='media-assets')
    def media_assets(self, request, pk=None):
        knowledge_base = self.get_object()
        if request.method == 'GET':
            queryset = (
                knowledge_base.media_assets
                .filter(tenant=knowledge_base.tenant)
                .select_related('resource')
                .order_by('-priority', '-updated_at', '-id')
            )
            serializer = KnowledgeMediaAssetSerializer(
                queryset,
                many=True,
                context={**self.get_serializer_context(), 'request': request},
            )
            return Response(serializer.data)

        serializer = KnowledgeMediaAssetCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        resources = list(
            Resource.objects.filter(
                tenant=knowledge_base.tenant,
                id__in=serializer.validated_data['resourceIds'],
                resource_type__in=[Resource.TYPE_IMAGE, Resource.TYPE_VIDEO],
            )
        )
        resources_by_id = {resource.id: resource for resource in resources}
        assets: list[KnowledgeMediaAsset] = []
        for resource_id in serializer.validated_data['resourceIds']:
            resource = resources_by_id[resource_id]
            asset, _ = KnowledgeMediaAsset.objects.get_or_create(
                knowledge_base=knowledge_base,
                resource=resource,
                defaults={
                    'tenant': knowledge_base.tenant,
                    'resource_type': resource.resource_type,
                    'resource_name': resource.name,
                    'created_by': request.user,
                },
            )
            enqueue_media_asset_index(asset)
            assets.append(asset)

        self.clear_cached_business_responses()
        output = KnowledgeMediaAssetSerializer(
            assets,
            many=True,
            context={**self.get_serializer_context(), 'request': request},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'media-assets/(?P<asset_id>[^/.]+)')
    def media_asset_detail(self, request, pk=None, asset_id=None):
        knowledge_base = self.get_object()
        asset = (
            knowledge_base.media_assets
            .filter(tenant=knowledge_base.tenant, pk=asset_id)
            .select_related('resource')
            .first()
        )
        if asset is None:
            return Response({'status': 'error', 'message': '配套素材不存在', 'code': 404}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            asset.delete()
            self.clear_cached_business_responses()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = KnowledgeMediaAssetSerializer(
            asset,
            data=request.data,
            partial=True,
            context={**self.get_serializer_context(), 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.clear_cached_business_responses()
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='index')
    def index(self, request, pk=None):
        knowledge_base = self.get_object()
        documents = list(knowledge_base.documents.filter(tenant=knowledge_base.tenant).order_by('id'))
        media_assets = list(knowledge_base.media_assets.filter(tenant=knowledge_base.tenant).order_by('id'))
        document_results = [enqueue_document_index(document, force=True) for document in documents]
        media_asset_results = [enqueue_media_asset_index(asset, force=True) for asset in media_assets]
        self.clear_cached_business_responses()
        return Response({
            'queuedCount': len(document_results) + len(media_asset_results),
            'documents': document_results,
            'mediaAssets': media_asset_results,
        })


@extend_schema_view(
    list=extend_schema(
        tags=['KnowledgeBase'],
        parameters=[
            OpenApiParameter(name='keyword', description='按标题/文件名模糊搜索', required=False, type=str),
        ],
    ),
    retrieve=extend_schema(tags=['KnowledgeBase']),
    create=extend_schema(tags=['KnowledgeBase']),
    destroy=extend_schema(tags=['KnowledgeBase']),
    index=extend_schema(tags=['KnowledgeBase']),
)
class KnowledgeDocumentViewSet(
    CachedBusinessResponseMixin,
    TenantScopedQuerysetMixin,
    PermissionMappedViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = KnowledgeDocumentSerializer
    queryset = KnowledgeDocument.objects.select_related('uploaded_by', 'knowledge_base').order_by('-updated_at', '-id')
    business_cache_namespace = 'knowledge_base'
    permission_map = {
        'list': [CanViewKnowledgeBase],
        'retrieve': [CanViewKnowledgeBase],
        'create': [CanUploadKnowledgeBase],
        'destroy': [CanUploadKnowledgeBase],
        'download': [CanDownloadKnowledgeBase],
        'bulk_download': [CanBulkDownloadKnowledgeBase],
        'index': [CanUploadKnowledgeBase],
    }
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = self.request_tenant
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(file_name__icontains=keyword))

        raw_knowledge_base_id = self.request.query_params.get('knowledge_base')
        if raw_knowledge_base_id:
            queryset = queryset.filter(knowledge_base_id=raw_knowledge_base_id)
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        document = serializer.save(**self.tenant_create_kwargs())
        self.clear_cached_business_responses()
        notify_knowledge_document_event('create', getattr(self.request, 'user', None), document)
        enqueue_document_index(document)

    def perform_destroy(self, instance: KnowledgeDocument):
        document_id = instance.pk
        document_title = instance.title
        document_file_name = instance.file_name
        company_name = str(getattr(getattr(instance, 'tenant', None), 'name', '') or '').strip()
        file_field = instance.file if instance.file else None
        super().perform_destroy(instance)
        if file_field:
            file_field.delete(save=False)
        notify_knowledge_document_deleted(
            getattr(self.request, 'user', None),
            document_id=document_id,
            title=document_title,
            file_name=document_file_name,
            company_name=company_name,
        )

    @extend_schema(
        tags=['KnowledgeBase'],
        responses={200: OpenApiResponse(description='二进制文件响应')},
    )
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        document = self.get_object()
        if not document.file:
            raise serializers.ValidationError('当前文档文件不存在')

        file_handle = document.file.open('rb')
        KnowledgeDocument.objects.filter(pk=document.pk).update(download_count=F('download_count') + 1)
        clear_business_cache_namespace(self.business_cache_namespace)
        notify_knowledge_document_event('download', request.user, document)

        response = FileResponse(file_handle, as_attachment=True, filename=document.file_name or f'{document.title}.bin')
        response['Content-Disposition'] = build_content_disposition(document.file_name or f'{document.title}.bin')
        return response

    @extend_schema(
        tags=['KnowledgeBase'],
        request={'application/json': {'type': 'object', 'properties': {'ids': {'type': 'array', 'items': {'type': 'integer'}}}}},
        responses={200: OpenApiResponse(description='ZIP 二进制响应')},
    )
    @action(detail=False, methods=['post'], url_path='bulk-download')
    def bulk_download(self, request):
        raw_ids = request.data.get('ids')
        if not isinstance(raw_ids, list):
            raise serializers.ValidationError('请至少选择一个有效文档')

        deduped_ids: list[int] = []
        seen_ids: set[int] = set()
        for raw_id in raw_ids:
            try:
                document_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if document_id in seen_ids:
                continue
            seen_ids.add(document_id)
            deduped_ids.append(document_id)

        # 走租户作用域查询集（修复跨租户泄漏：原先直接 KnowledgeDocument.objects 绕过隔离，
        # B 公司可凭 id 批量下载 A 公司文档）。
        documents_by_id = {
            document.id: document
            for document in self.get_queryset().filter(id__in=deduped_ids).order_by('-updated_at', '-id')
        }
        valid_documents = [
            document
            for document_id in deduped_ids
            for document in [documents_by_id.get(document_id)]
            if document and document.file
        ]

        if not valid_documents:
            raise serializers.ValidationError('请至少选择一个有效文档')
        if len(valid_documents) > MAX_BULK_DOWNLOAD_COUNT:
            raise serializers.ValidationError('单次最多下载 20 个文档')

        total_size = sum(get_document_size(document) for document in valid_documents)
        if total_size > MAX_BULK_DOWNLOAD_SIZE:
            raise serializers.ValidationError('所选文档总大小不能超过 200MB')

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file_path = temp_file.name
        temp_file.close()
        archive_names: set[str] = set()
        try:
            with zipfile.ZipFile(temp_file_path, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                for document in valid_documents:
                    archive_name = build_zip_entry_name(document.file_name or f'{document.title}.bin', archive_names)
                    with document.file.open('rb') as file_handle:
                        zip_file.writestr(archive_name, file_handle.read())
        except Exception:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise

        KnowledgeDocument.objects.filter(pk__in=[document.pk for document in valid_documents]).update(download_count=F('download_count') + 1)
        clear_business_cache_namespace(self.business_cache_namespace)
        notify_knowledge_bulk_download(request.user, valid_documents)

        zip_name = f"knowledge-base-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}.zip"
        response = FileResponse(open(temp_file_path, 'rb'), as_attachment=True, content_type='application/zip')
        response['Content-Disposition'] = build_content_disposition(zip_name)
        response._resource_closers.append(lambda path=temp_file_path: os.path.exists(path) and os.remove(path))
        return response

    @extend_schema(
        tags=['KnowledgeBase'],
        responses={200: OpenApiResponse(description='文档索引重建已触发')},
    )
    @action(detail=True, methods=['post'], url_path='index')
    def index(self, request, pk=None):
        document = self.get_object()
        result = enqueue_document_index(document, force=True)
        self.clear_cached_business_responses()
        return Response(result)
