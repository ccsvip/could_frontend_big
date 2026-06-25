from __future__ import annotations

from pathlib import Path

from rest_framework import serializers

from .models import KnowledgeBase, KnowledgeDocument

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

    class Meta:
        model = KnowledgeBase
        fields = (
            'id',
            'name',
            'description',
            'documentCount',
            'createdBy',
            'isActive',
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
    topN = serializers.IntegerField(required=False, min_value=1, max_value=20, default=5)
