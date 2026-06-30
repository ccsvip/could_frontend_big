from django.contrib import admin
from django.utils.html import format_html

from config.business_cache import clear_business_cache_namespace

from .models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk, KnowledgeMediaAsset


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'is_active', 'retrieval_min_score', 'created_by', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('name', 'description')
    raw_id_fields = ('tenant', 'created_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'file_name',
        'file_extension',
        'knowledge_base',
        'index_status',
        'chunk_count',
        'uploaded_by',
        'download_count',
        'updated_at',
    )
    search_fields = ('title', 'file_name', 'description')
    list_filter = ('file_extension', 'knowledge_base', 'index_status', 'updated_at')
    readonly_fields = (
        'created_at',
        'updated_at',
        'file_name',
        'file_extension',
        'file_size',
        'index_status',
        'index_error',
        'indexed_at',
        'chunk_count',
        'index_model',
        'uploaded_by',
        'download_count',
        'file_link',
    )
    list_per_page = 20
    fieldsets = (
        ('基础信息', {'fields': ('title', 'description', 'knowledge_base', 'uploaded_by', 'download_count')}),
        ('文件信息', {'fields': ('file', 'file_link', 'file_name', 'file_extension', 'file_size')}),
        ('索引信息', {'fields': ('index_status', 'index_error', 'indexed_at', 'chunk_count', 'index_model')}),
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


@admin.register(KnowledgeMediaAsset)
class KnowledgeMediaAssetAdmin(admin.ModelAdmin):
    list_display = ('resource_name', 'resource_type', 'knowledge_base', 'tenant', 'embedding_status', 'is_enabled', 'priority', 'updated_at')
    list_filter = ('resource_type', 'embedding_status', 'is_enabled', 'updated_at')
    search_fields = ('resource_name', 'keywords', 'description', 'vlm_description', 'vlm_keywords', 'knowledge_base__name')
    raw_id_fields = ('tenant', 'knowledge_base', 'resource', 'created_by')
    readonly_fields = (
        'resource_type',
        'resource_name',
        'vlm_description',
        'vlm_keywords',
        'embedding_status',
        'embedding_error',
        'embedding_model',
        'embedding_processed_at',
        'created_at',
        'updated_at',
    )
    list_per_page = 30
