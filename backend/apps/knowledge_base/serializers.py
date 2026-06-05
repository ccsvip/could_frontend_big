from __future__ import annotations

from pathlib import Path

from rest_framework import serializers

from .models import KnowledgeDocument

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


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=True)
    fileName = serializers.CharField(source='file_name', read_only=True)
    fileExtension = serializers.CharField(source='file_extension', read_only=True)
    fileSize = serializers.IntegerField(source='file_size', read_only=True, allow_null=True)
    processingStatus = serializers.CharField(source='processing_status', read_only=True)
    processingStatusLabel = serializers.CharField(source='get_processing_status_display', read_only=True)
    processingResult = serializers.CharField(source='processing_result', read_only=True)
    uploadedBy = serializers.SerializerMethodField()
    downloadCount = serializers.IntegerField(source='download_count', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = (
            'id',
            'title',
            'description',
            'file',
            'fileName',
            'fileExtension',
            'fileSize',
            'processingStatus',
            'processingStatusLabel',
            'processingResult',
            'uploadedBy',
            'downloadCount',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'fileName',
            'fileExtension',
            'fileSize',
            'processingStatus',
            'processingStatusLabel',
            'processingResult',
            'uploadedBy',
            'downloadCount',
            'created_at',
            'updated_at',
        )
        extra_kwargs = {
            'title': {'required': False, 'allow_blank': True},
            'description': {'required': False, 'allow_blank': True},
        }

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


class KnowledgeDocumentReviewSerializer(serializers.Serializer):
    processingStatus = serializers.ChoiceField(
        source='processing_status',
        choices=(KnowledgeDocument.STATUS_APPROVED, KnowledgeDocument.STATUS_REJECTED),
    )
    processingResult = serializers.CharField(source='processing_result', required=False, allow_blank=True)

