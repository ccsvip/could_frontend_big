from django.contrib import admin
from django.conf import settings

from .models import AppRelease, AppUpdateEvent


class SuperuserOnlyAdminMixin:
    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)


@admin.register(AppRelease)
class AppReleaseAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('version_name', 'version_code', 'file_name', 'file_size', 'force_upgrade_version_code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('release_id', 'version_name', 'version_info', 'file_name', 'sha256')
    list_editable = ('is_active',)
    ordering = ('-version_code',)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        derived = ('release_id', 'package_name', 'file_name', 'file_size', 'sha256', 'created_by', 'created_at', 'updated_at')
        if obj is None:
            return derived
        return (
            *derived, 'version_name', 'version_code', 'version_info',
            'apk_file', 'force_upgrade_version_code', 'release_notes',
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.package_name = getattr(settings, 'APP_UPDATE_PACKAGE_NAME', 'com.solin.digital')
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AppUpdateEvent)
class AppUpdateEventAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('device', 'release', 'state', 'current_version_code', 'target_version_code', 'occurred_at')
    list_filter = ('state', 'occurred_at')
    search_fields = ('device__code', 'release__release_id', 'message')
    readonly_fields = tuple(field.name for field in AppUpdateEvent._meta.fields)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
