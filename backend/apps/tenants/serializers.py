from rest_framework import serializers

from apps.accounts.models import Menu, PermissionPoint

from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    isLegacy = serializers.BooleanField(source='is_legacy', read_only=True)
    menuCount = serializers.SerializerMethodField()
    memberCount = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ('id', 'name', 'code', 'isActive', 'isLegacy', 'menuCount', 'memberCount', 'created_at', 'updated_at')
        read_only_fields = ('id', 'code', 'isLegacy', 'menuCount', 'memberCount', 'created_at', 'updated_at')

    def get_menuCount(self, obj: Tenant) -> int:
        return obj.menus.count()

    def get_memberCount(self, obj: Tenant) -> int:
        return obj.memberships.count()


class TenantCreateSerializer(serializers.ModelSerializer):
    """超管手工建公司（区别于审批建公司）。code 由后端按 name 生成唯一 slug。"""

    class Meta:
        model = Tenant
        fields = ('id', 'name')

    def create(self, validated_data):
        from .services import generate_unique_tenant_code
        name = validated_data['name']
        return Tenant.objects.create(name=name, code=generate_unique_tenant_code(name))


class TenantMenuAssignmentSerializer(serializers.Serializer):
    """超管给公司分配菜单 + 权限点。

    菜单必须是 audience='all'（可分配业务菜单）；平台/公司管理员专属菜单不可分配。
    权限点是公司可用能力的上限（员工实际权限再按角色取交集）。
    """

    menuIds = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    permissionPointIds = serializers.ListField(child=serializers.IntegerField(), allow_empty=True, required=False, default=list)

    def validate_menuIds(self, value):
        assignable = set(
            Menu.objects.filter(id__in=value, audience=Menu.AUDIENCE_ALL).values_list('id', flat=True)
        )
        invalid = set(value) - assignable
        if invalid:
            raise serializers.ValidationError(f'包含不可分配的菜单（仅允许通用业务菜单）：{sorted(invalid)}')
        return value

    def validate_permissionPointIds(self, value):
        existing = set(PermissionPoint.objects.filter(id__in=value).values_list('id', flat=True))
        invalid = set(value) - existing
        if invalid:
            raise serializers.ValidationError(f'包含不存在的权限点：{sorted(invalid)}')
        return value

    def save(self, tenant: Tenant):
        tenant.menus.set(Menu.objects.filter(id__in=self.validated_data['menuIds']))
        tenant.permission_points.set(
            PermissionPoint.objects.filter(id__in=self.validated_data.get('permissionPointIds', []))
        )
        return tenant


class MenuCatalogItemSerializer(serializers.ModelSerializer):
    """可分配菜单目录项（供超管分配器使用）。"""

    class Meta:
        model = Menu
        fields = ('id', 'name', 'key', 'path', 'icon', 'parent', 'sort_order')


class PermissionPointCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionPoint
        fields = ('id', 'name', 'code', 'module')
