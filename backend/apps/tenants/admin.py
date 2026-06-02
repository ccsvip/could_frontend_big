from django.contrib import admin

from .models import Membership, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'is_legacy', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active', 'is_legacy')
    filter_horizontal = ('menus', 'permission_points')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'is_tenant_admin', 'must_change_password', 'updated_at')
    search_fields = ('user__username', 'user__first_name', 'tenant__name', 'tenant__code')
    list_filter = ('tenant', 'is_tenant_admin', 'must_change_password')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
