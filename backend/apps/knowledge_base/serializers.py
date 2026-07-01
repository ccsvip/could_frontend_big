from __future__ import annotations

from pathlib import Path

from rest_framework import serializers

from apps.resources.models import Resource
from apps.resources.serializers import build_absolute_file_url

from .models import KnowledgeBase, KnowledgeDocument, KnowledgeMediaAsset

ALLOWED_DOCUMENT_EXTENSIONS = {
    '.doc',
    '.docx',
    '.ppt',
    '.pptx',
    '.md',
    '.txt',
    '.pdf',
    '.xls',
    '.xlsx',
}
ALLOWED_DOCUMENT_TYPES_MESSAGE = '仅支持 doc/docx/ppt/pptx/md/txt/pdf/xls/xlsx 等文档格式'


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    documentCount = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', required=False)
    chunkSize = serializers.IntegerField(source='chunk_size', required=False, min_value=100, max_value=4000)
    chunkOverlap = serializers.IntegerField(source='chunk_overlap', required=False, min_value=0, max_value=1000)
    retrievalTopN = serializers.IntegerField(source='retrieval_top_n', required=False, min_value=1, max_value=20)
    retrievalMinScore = serializers.FloatField(source='retrieval_min_score', required=False, min_value=0, max_value=1)

    class Meta:
        model = KnowledgeBase
        fields = (
            'id',
            'name',
            'description',
            'documentCount',
            'createdBy',
            'isActive',
            'chunkSize',
            'chunkOverlap',
            'retrievalTopN',
            'retrievalMinScore',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'documentCount', 'createdBy', 'created_at', 'updated_at')

    def get_createdBy(self, obj: KnowledgeBase) -> str:
        if obj.created_by is None:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.username

    def get_documentCount(self, obj: KnowledgeBase) -> int:
        value = getattr(obj, 'document_count', None)
        if value is not None:
            return int(value)
        return obj.documents.count()

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('知识库名称不能为空')
        tenant = self.context.get('tenant')
        if tenant is not None:
            queryset = KnowledgeBase.objects.filter(tenant=tenant, name=value)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError('同名知识库已存在')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        chunk_size = attrs.get('chunk_size', self.instance.chunk_size if self.instance else 500)
        chunk_overlap = attrs.get('chunk_overlap', self.instance.chunk_overlap if self.instance else 50)
        if chunk_overlap >= chunk_size:
            raise serializers.ValidationError({'chunkOverlap': '分块重叠必须小于分块长度'})
        return attrs


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=True)
    knowledgeBaseId = serializers.PrimaryKeyRelatedField(
        source='knowledge_base',
        queryset=KnowledgeBase.objects.none(),
        required=False,
        allow_null=True,
    )
    knowledgeBaseName = serializers.CharField(source='knowledge_base.name', read_only=True, default='')
    fileName = serializers.CharField(source='file_name', read_only=True)
    fileExtension = serializers.CharField(source='file_extension', read_only=True)
    fileSize = serializers.IntegerField(source='file_size', read_only=True, allow_null=True)
    uploadedBy = serializers.SerializerMethodField()
    downloadCount = serializers.IntegerField(source='download_count', read_only=True)
    indexingStatus = serializers.CharField(source='index_status', read_only=True)
    indexingStatusLabel = serializers.CharField(source='get_index_status_display', read_only=True)
    indexingError = serializers.CharField(source='index_error', read_only=True)
    indexedAt = serializers.DateTimeField(source='indexed_at', read_only=True, allow_null=True)
    chunkCount = serializers.IntegerField(source='chunk_count', read_only=True)
    indexModel = serializers.CharField(source='index_model', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = (
            'id',
            'title',
            'description',
            'knowledgeBaseId',
            'knowledgeBaseName',
            'file',
            'fileName',
            'fileExtension',
            'fileSize',
            'uploadedBy',
            'downloadCount',
            'indexingStatus',
            'indexingStatusLabel',
            'indexingError',
            'indexedAt',
            'chunkCount',
            'indexModel',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'fileName',
            'fileExtension',
            'fileSize',
            'uploadedBy',
            'downloadCount',
            'indexingStatus',
            'indexingStatusLabel',
            'indexingError',
            'indexedAt',
            'chunkCount',
            'indexModel',
            'created_at',
            'updated_at',
        )
        extra_kwargs = {
            'title': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
        }

    def get_fields(self):
        fields = super().get_fields()
        tenant = self.context.get('tenant')
        if tenant is not None:
            fields['knowledgeBaseId'].queryset = KnowledgeBase.objects.for_tenant(tenant).filter(is_active=True)
        return fields

    def get_uploadedBy(self, obj: KnowledgeDocument) -> str:
        if obj.uploaded_by is None:
            return ''
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

    def validate_file(self, value):
        suffix = Path(value.name).suffix.lower()
        if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise serializers.ValidationError(ALLOWED_DOCUMENT_TYPES_MESSAGE)
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        uploaded_file = attrs.get('file')
        if uploaded_file and not attrs.get('title'):
            attrs['title'] = Path(uploaded_file.name).stem
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['uploaded_by'] = request.user
        return super().create(validated_data)


class KnowledgeRecallTestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
    topN = serializers.IntegerField(required=False, min_value=1, max_value=20)


class KnowledgeMediaAssetSerializer(serializers.ModelSerializer):
    resourceId = serializers.IntegerField(source='resource_id', read_only=True)
    resourceName = serializers.CharField(source='resource_name', read_only=True)
    resourceType = serializers.CharField(source='resource_type', read_only=True)
    resourceTypeLabel = serializers.SerializerMethodField()
    isEnabled = serializers.BooleanField(source='is_enabled', required=False)
    isMissing = serializers.BooleanField(source='is_missing', read_only=True)
    vlmDescription = serializers.CharField(source='vlm_description', read_only=True)
    vlmKeywords = serializers.CharField(source='vlm_keywords', read_only=True)
    embeddingStatus = serializers.CharField(source='embedding_status', read_only=True)
    embeddingStatusLabel = serializers.CharField(source='get_embedding_status_display', read_only=True)
    embeddingError = serializers.CharField(source='embedding_error', read_only=True)
    embeddingModel = serializers.CharField(source='embedding_model', read_only=True)
    embeddingProcessedAt = serializers.DateTimeField(source='embedding_processed_at', read_only=True, allow_null=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeMediaAsset
        fields = (
            'id',
            'resourceId',
            'resourceName',
            'resourceType',
            'resourceTypeLabel',
            'keywords',
            'description',
            'vlmDescription',
            'vlmKeywords',
            'isEnabled',
            'priority',
            'isMissing',
            'embeddingStatus',
            'embeddingStatusLabel',
            'embeddingError',
            'embeddingModel',
            'embeddingProcessedAt',
            'url',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'resourceId',
            'resourceName',
            'resourceType',
            'resourceTypeLabel',
            'isMissing',
            'vlmDescription',
            'vlmKeywords',
            'embeddingStatus',
            'embeddingStatusLabel',
            'embeddingError',
            'embeddingModel',
            'embeddingProcessedAt',
            'url',
            'created_at',
            'updated_at',
        )

    def get_resourceTypeLabel(self, obj: KnowledgeMediaAsset) -> str:
        if obj.resource is not None:
            return obj.resource.get_resource_type_display()
        return {'image': '图片', 'video': '视频'}.get(obj.resource_type, obj.resource_type)

    def get_url(self, obj: KnowledgeMediaAsset) -> str:
        resource = obj.resource
        if resource is None:
            return ''
        if resource.object_key:
            from apps.resources.services.minio_client import build_public_object_url

            return build_public_object_url(resource.object_key, backend=resource.storage_backend)
        file_url = build_absolute_file_url(self.context.get('request'), resource.file)
        if file_url:
            return file_url
        return resource.cloud_url or ''

    def validate_keywords(self, value: str) -> str:
        return str(value or '').strip()

    def validate_description(self, value: str) -> str:
        return str(value or '').strip()


class KnowledgeMediaAssetCreateSerializer(serializers.Serializer):
    resourceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_resourceIds(self, value: list[int]) -> list[int]:
        deduped: list[int] = []
        seen: set[int] = set()
        for resource_id in value:
            if resource_id in seen:
                continue
            seen.add(resource_id)
            deduped.append(resource_id)
        tenant = self.context.get('tenant')
        resources = Resource.objects.filter(
            id__in=deduped,
            resource_type__in=[Resource.TYPE_IMAGE, Resource.TYPE_VIDEO],
        )
        if tenant is None:
            resources = resources.filter(tenant__isnull=True)
        else:
            resources = resources.filter(tenant=tenant)
        found_ids = set(resources.values_list('id', flat=True))
        missing_ids = [resource_id for resource_id in deduped if resource_id not in found_ids]
        if missing_ids:
            raise serializers.ValidationError('请选择当前公司下存在的图片或视频素材')
        return deduped
