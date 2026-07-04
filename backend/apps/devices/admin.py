from django.contrib import admin

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceChatLog, DeviceGroup, WakeWord


@admin.register(DeviceGroup)
class DeviceGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'created_at')
    search_fields = ('name', 'remark')
    list_filter = ('tenant',)


@admin.register(DeviceApplication)
class DeviceApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'tenant', 'is_active', 'updated_at')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name', 'code', 'description')
    filter_horizontal = ('resources', 'scrolling_texts', 'voice_tones', 'tts_voices', 'model_assets', 'command_groups')


@admin.register(DeviceAuthorizationCode)
class DeviceAuthorizationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'application', 'tenant', 'status', 'authorization_type', 'expires_at', 'used_by_device')
    list_filter = ('tenant', 'status', 'authorization_type', 'expires_at')
    search_fields = ('code', 'application__name', 'used_by_device__code', 'remark')
    autocomplete_fields = ('application', 'used_by_device', 'created_by')


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'application',
        'agent_application',
        'group',
        'status',
        'authorization_type',
        'expires_at',
        'software_version',
        'system_version',
        'last_heartbeat',
    )
    list_filter = ('tenant', 'status', 'authorization_type', 'application', 'agent_application', 'group', 'is_enabled')
    search_fields = ('code', 'name', 'software_version', 'system_version', 'mainboard_info')
    autocomplete_fields = ('application', 'agent_application', 'group')


@admin.register(DeviceAuthLog)
class DeviceAuthLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'code', 'result', 'message', 'tenant', 'application', 'agent_application', 'device')
    list_filter = ('action', 'result', 'tenant', 'application', 'agent_application', 'created_at')
    search_fields = ('code', 'message', 'device__name', 'device__code')
    readonly_fields = ('created_at',)


@admin.register(DeviceChatLog)
class DeviceChatLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'source', 'code', 'tenant', 'application', 'agent_application', 'model_name')
    list_filter = ('source', 'tenant', 'application', 'agent_application', 'created_at')
    search_fields = ('code', 'device__name', 'device__code', 'question_text', 'answer_text', 'request_id', 'trace_id')
    readonly_fields = ('created_at',)


@admin.register(WakeWord)
class WakeWordAdmin(admin.ModelAdmin):
    list_display = ('text', 'tenant', 'boost', 'threshold', 'is_active', 'updated_at')
    list_filter = ('tenant', 'is_active')
    search_fields = ('text', 'encoded_text')
    filter_horizontal = ('devices',)
