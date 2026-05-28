from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import AccountApplication, Menu, PermissionPoint, Role, UserRole

User = get_user_model()


# 接管默认 User admin，给列表页加显眼的"重置密码"列。
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'reset_password_button',
    )

    @admin.display(description='重置密码')
    def reset_password_button(self, obj):
        url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" '
            'style="background:#0d9488;color:#fff;padding:4px 10px;border-radius:4px;'
            'text-decoration:none;font-size:12px;white-space:nowrap;">'
            '🔑 重置密码</a>',
            url,
        )


@admin.register(AccountApplication)
class AccountApplicationAdmin(admin.ModelAdmin):
    list_display = ('username', 'applicant_name', 'enterprise_name', 'phone', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('username', 'applicant_name', 'enterprise_name', 'phone')
    readonly_fields = ('password', 'created_at', 'updated_at')


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'path', 'parent', 'sort_order', 'is_active', 'updated_at')
    search_fields = ('name', 'key', 'path')
    list_filter = ('is_active', 'parent')
    ordering = ('sort_order', 'id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PermissionPoint)
class PermissionPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'module', 'is_active', 'updated_at')
    search_fields = ('name', 'code', 'module')
    list_filter = ('module', 'is_active')
    ordering = ('module', 'code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'updated_at')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)
    filter_horizontal = ('menus', 'permission_points')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'updated_at')
    search_fields = ('user__username', 'user__first_name', 'role__name', 'role__code')
    list_filter = ('role',)
    autocomplete_fields = ('user', 'role')
    readonly_fields = ('created_at', 'updated_at')
