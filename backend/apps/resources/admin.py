from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CommandGroup,
    ControlCommand,
    MinioConfig,
    ModelAsset,
    Resource,
    ScrollingText,
    ScrollingTextItem,
    TaskCommand,
    TaskCommandStep,
    TenantVideoQuota,
    VoiceTone,
)
from .point_models import Point


@admin.register(CommandGroup)
class CommandGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group_type', 'export_enabled', 'is_active', 'updated_at')
    search_fields = ('name',)
    list_filter = ('group_type', 'export_enabled', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20


@admin.register(ControlCommand)
class ControlCommandAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'command_code', 'command_value_type', 'protocol', 'host', 'port', 'is_active', 'updated_at')
    search_fields = ('name', 'command_code', 'host')
    list_filter = ('group', 'command_value_type', 'protocol', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('group',)
    list_per_page = 20


class TaskCommandStepInline(admin.TabularInline):
    model = TaskCommandStep
    extra = 1
    autocomplete_fields = ('control_command', 'point', 'resource')
    fields = ('parent', 'order', 'task_type', 'control_command', 'point', 'resource', 'text_content', 'image_text', 'delay_seconds', 'wait_for_inner_tasks')
    ordering = ('parent_id', 'order', 'id')


@admin.register(TaskCommand)
class TaskCommandAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'command_code', 'is_active', 'task_count', 'updated_at')
    search_fields = ('name', 'command_code')
    list_filter = ('group', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('group',)
    inlines = (TaskCommandStepInline,)
    list_per_page = 20

    @admin.display(description='子任务数量')
    def task_count(self, obj: TaskCommand) -> int:
        return obj.tasks.count()


@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display = ('name', 'command', 'is_active', 'is_show', 'updated_at')
    list_editable = ('is_show',)
    search_fields = ('name', 'command')
    list_filter = ('is_active', 'is_show', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20


@admin.register(ModelAsset)
class ModelAssetAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'model_type',
        'orientation',
        'is_visible',
        'has_model_file_display',
        'has_thumbnail_display',
        'model_size_display',
        'updated_at',
    )
    search_fields = ('name', 'cloud_url', 'model_file')
    list_filter = ('model_type', 'orientation', 'is_visible', 'updated_at')
    readonly_fields = (
        'created_at',
        'updated_at',
        'model_size_display',
        'local_url_display',
        'has_model_file_display',
        'has_thumbnail_display',
    )
    list_per_page = 10

    @admin.display(boolean=True, description='是否已上传缩略图')
    def has_thumbnail_display(self, obj: ModelAsset) -> bool:
        return obj.has_thumbnail

    @admin.display(boolean=True, description='是否已上传模型文件')
    def has_model_file_display(self, obj: ModelAsset) -> bool:
        return obj.has_model_file

    @admin.display(description='模型大小')
    def model_size_display(self, obj: ModelAsset) -> str:
        if obj.model_size is None:
            return '未自动计算'
        return f'{obj.model_size} 字节'

    @admin.display(description='本地地址')
    def local_url_display(self, obj: ModelAsset) -> str:
        if not obj.model_file:
            return '未生成本地地址'
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', obj.model_file.url, obj.model_file.url)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'resource_type', 'category', 'has_file_display', 'updated_at')
    search_fields = ('name', 'description', 'file', 'cloud_url')
    list_filter = ('resource_type', 'category', 'updated_at')
    readonly_fields = ('created_at', 'updated_at', 'has_file_display')
    list_per_page = 10

    @admin.display(boolean=True, description='是否已上传文件')
    def has_file_display(self, obj: Resource) -> bool:
        return obj.has_file


class ScrollingTextItemInline(admin.TabularInline):
    model = ScrollingTextItem
    extra = 1
    fields = ('order', 'zh_text', 'en_text')
    ordering = ('order', 'id')


@admin.register(ScrollingText)
class ScrollingTextAdmin(admin.ModelAdmin):
    list_display = ('title', 'i18n_scheme', 'is_active', 'item_count', 'updated_at')
    search_fields = ('title', 'items__zh_text', 'items__en_text')
    list_filter = ('i18n_scheme', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (ScrollingTextItemInline,)
    list_per_page = 10

    @admin.display(description='文本条数')
    def item_count(self, obj: ScrollingText) -> int:
        return obj.items.count()


@admin.register(VoiceTone)
class VoiceToneAdmin(admin.ModelAdmin):
    list_display = ('name', 'voice_code', 'is_visible', 'is_active', 'has_icon_display', 'has_audio_display', 'updated_at')
    search_fields = ('name', 'voice_code', 'content')
    list_filter = ('is_visible', 'is_active', 'updated_at')
    readonly_fields = ('created_at', 'updated_at', 'has_icon_display', 'has_audio_display')
    list_per_page = 10

    @admin.display(boolean=True, description='是否已上传图标')
    def has_icon_display(self, obj: VoiceTone) -> bool:
        return obj.has_icon

    @admin.display(boolean=True, description='是否已上传音频')
    def has_audio_display(self, obj: VoiceTone) -> bool:
        return obj.has_audio


@admin.register(MinioConfig)
class MinioConfigAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'bucket_name', 'is_active', 'video_max_size_mb', 'updated_at')
    fieldsets = (
        ('连接信息', {
            'fields': ('endpoint', 'secure', 'region', 'access_key', 'secret_key'),
            'description': '字段留空时回退 backend/.env 里的同名 MINIO_* 配置。',
        }),
        ('Bucket / 访问', {
            'fields': ('bucket_name', 'public_base_url', 'is_active'),
        }),
        ('上传约束', {
            'fields': ('video_max_size_mb',),
        }),
        ('元信息', {
            'fields': ('updated_at',),
        }),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not MinioConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        from django.urls import reverse

        instance = MinioConfig.load()
        return redirect(reverse('admin:resources_minioconfig_change', args=[instance.pk]))


@admin.register(TenantVideoQuota)
class TenantVideoQuotaAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'quota_mb', 'updated_at')
    search_fields = ('tenant__name', 'tenant__code')
    autocomplete_fields = ('tenant',)
    readonly_fields = ('updated_at',)
