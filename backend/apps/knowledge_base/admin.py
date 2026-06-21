from django.contrib import admin
from django.utils.html import format_html

from config.business_cache import clear_business_cache_namespace

from .models import KnowledgeDocument, KnowledgeDocumentChunk


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'file_name',
        'file_extension',
        'processing_status',
        'uploaded_by',
        'download_count',
        'updated_at',
    )
    search_fields = ('title', 'file_name', 'description', 'processing_result')
    list_filter = ('processing_status', 'file_extension', 'updated_at')
    readonly_fields = (
        'created_at',
        'updated_at',
        'file_name',
        'file_extension',
        'file_size',
        'uploaded_by',
        'download_count',
        'file_link',
    )
    list_per_page = 20
    fieldsets = (
        ('基础信息', {'fields': ('title', 'description', 'uploaded_by', 'download_count')}),
        ('文件信息', {'fields': ('file', 'file_link', 'file_name', 'file_extension', 'file_size')}),
        ('处理信息', {'fields': ('processing_status', 'processing_result')}),
        ('时间信息', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='文件链接')
    def file_link(self, obj: KnowledgeDocument) -> str:
        if not obj.file:
            return '暂无文件'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            obj.file.url,
            obj.file_name or obj.file.url,
        )

    def save_model(self, request, obj: KnowledgeDocument, form, change):
        super().save_model(request, obj, form, change)
        clear_business_cache_namespace('knowledge_base')


@admin.register(KnowledgeDocumentChunk)
class KnowledgeDocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'chunk_index', 'embedding_model', 'updated_at')
    list_filter = ('embedding_model', 'updated_at')
    search_fields = ('document__title', 'content')
    readonly_fields = ('tenant', 'document', 'chunk_index', 'content_hash', 'embedding_model', 'created_at', 'updated_at')
    list_per_page = 30
