from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

from django.db.models import F, Q
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import (
    CanBulkDownloadKnowledgeBase,
    CanDownloadKnowledgeBase,
    CanUploadKnowledgeBase,
    CanViewKnowledgeBase,
    IsSuperUser,
)
from config.business_cache import CachedBusinessResponseMixin, clear_business_cache_namespace
from apps.tenants.mixins import TenantScopedQuerysetMixin

from .models import KnowledgeDocument
from .serializers import KnowledgeDocumentReviewSerializer, KnowledgeDocumentSerializer
from .services import (
    notify_knowledge_bulk_download,
    notify_knowledge_document_deleted,
    notify_knowledge_document_event,
    notify_knowledge_document_reviewed,
)

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


@extend_schema_view(
    list=extend_schema(
        tags=['KnowledgeBase'],
        parameters=[
            OpenApiParameter(name='keyword', description='按标题/文件名模糊搜索', required=False, type=str),
            OpenApiParameter(name='processing_status', description='按处理状态过滤', required=False, type=str),
        ],
    ),
    retrieve=extend_schema(tags=['KnowledgeBase']),
    create=extend_schema(tags=['KnowledgeBase']),
    destroy=extend_schema(tags=['KnowledgeBase']),
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
    queryset = KnowledgeDocument.objects.select_related('uploaded_by').order_by('-updated_at', '-id')
    business_cache_namespace = 'knowledge_base'
    permission_map = {
        'list': [CanViewKnowledgeBase],
        'retrieve': [CanViewKnowledgeBase],
        'create': [CanUploadKnowledgeBase],
        'destroy': [CanUploadKnowledgeBase],
        'download': [CanDownloadKnowledgeBase],
        'bulk_download': [CanBulkDownloadKnowledgeBase],
        'review': [IsSuperUser],
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(file_name__icontains=keyword))

        processing_status = self.request.query_params.get('processing_status', '').strip()
        if processing_status:
            queryset = queryset.filter(processing_status=processing_status)
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        document = serializer.save(**self.tenant_create_kwargs())
        self.clear_cached_business_responses()
        notify_knowledge_document_event('create', getattr(self.request, 'user', None), document)

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
        request=KnowledgeDocumentReviewSerializer,
        responses={200: KnowledgeDocumentSerializer},
    )
    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, pk=None):
        document = self.get_object()
        serializer = KnowledgeDocumentReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document.processing_status = serializer.validated_data['processing_status']
        document.processing_result = serializer.validated_data.get('processing_result', '')
        document.save(update_fields=['processing_status', 'processing_result', 'updated_at'])
        clear_business_cache_namespace(self.business_cache_namespace)
        notify_knowledge_document_reviewed(request.user, document)
        return Response(
            {
                'status': 'success',
                'message': '审核操作成功',
                'data': KnowledgeDocumentSerializer(document, context={'request': request}).data,
            }
        )
