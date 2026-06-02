from django.contrib import admin

from .models import OperationLog


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ('actor_username', 'tenant', 'action', 'method', 'path', 'status_code', 'created_at')
    list_filter = ('action', 'method', 'status_code', 'created_at')
    search_fields = ('actor_username', 'path')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
