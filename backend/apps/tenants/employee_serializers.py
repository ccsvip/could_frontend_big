from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from rest_framework import serializers

from apps.accounts.models import Menu, PermissionPoint, Role, UserRole

from .models import Membership

User = get_user_model()


def _tenant_from_context(serializer) -> object:
    request = serializer.context['request']
    from .services import get_user_tenant
    return get_user_tenant(request.user)


class EmployeeSerializer(serializers.Serializer):
    """员工读序列化（基于 auth.User + Membership + 绑定角色）。"""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    displayName = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    mustChangePassword = serializers.SerializerMethodField()
    roleId = serializers.SerializerMethodField()
    roleName = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source='date_joined', read_only=True)

    def get_displayName(self, obj) -> str:
        return obj.get_full_name() or obj.username

    def get_mustChangePassword(self, obj) -> bool:
        membership = getattr(obj, 'membership', None)
        return bool(membership and membership.must_change_password)

    def get_roleId(self, obj):
        binding = getattr(obj, 'role_binding', None)
        return binding.role_id if binding else None

    def get_roleName(self, obj):
        binding = getattr(obj, 'role_binding', None)
        return binding.role.name if binding else None


class EmployeeCreateSerializer(serializers.Serializer):
    username = serializers.RegexField(
        regex=r'^[A-Za-z0-9]{3,30}$',
        max_length=30,
        error_messages={'invalid': '用户名需为 3-30 位英文字母或数字'},
    )
    displayName = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128, write_only=True)
    roleId = serializers.IntegerField(required=False, allow_null=True)

    def validate_username(self, value: str) -> str:
        username = value.strip()
        # 用户名全局唯一（D1）：跨公司也不能重名，给友好提示。
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError('该用户名已被占用，请更换')
        return username

    def validate_password(self, value: str) -> str:
        if value.isdigit():
            raise serializers.ValidationError('密码不能为纯数字')
        if len(value) < 6:
            raise serializers.ValidationError('密码长度不能少于 6 位')
        password_validation.validate_password(value)
        return value

    def validate_roleId(self, value):
        if value is None:
            return value
        tenant = _tenant_from_context(self)
        # 只能绑定本公司的角色（防止绑到别家公司或平台模板）。
        if not Role.objects.filter(id=value, tenant=tenant).exists():
            raise serializers.ValidationError('指定角色不存在或不属于本公司')
        return value

    def create(self, validated_data):
        tenant = _tenant_from_context(self)
        user = User.objects.create(
            username=validated_data['username'],
            first_name=validated_data['displayName'],
            is_active=True,
        )
        user.set_password(validated_data['password'])
        user.save(update_fields=['password'])
        # 员工首次登录强制改密（D4）。
        Membership.objects.create(
            user=user, tenant=tenant, is_tenant_admin=False, must_change_password=True,
        )
        role_id = validated_data.get('roleId')
        if role_id:
            UserRole.objects.create(user=user, role_id=role_id)
        return user


class EmployeeUpdateSerializer(serializers.Serializer):
    displayName = serializers.CharField(max_length=64, required=False)
    isActive = serializers.BooleanField(required=False)
    roleId = serializers.IntegerField(required=False, allow_null=True)

    def validate_roleId(self, value):
        if value is None:
            return value
        tenant = _tenant_from_context(self)
        if not Role.objects.filter(id=value, tenant=tenant).exists():
            raise serializers.ValidationError('指定角色不存在或不属于本公司')
        return value

    def update(self, instance, validated_data):
        if 'displayName' in validated_data:
            instance.first_name = validated_data['displayName']
        if 'isActive' in validated_data:
            instance.is_active = validated_data['isActive']
        instance.save()
        if 'roleId' in validated_data:
            role_id = validated_data['roleId']
            if role_id is None:
                UserRole.objects.filter(user=instance).delete()
            else:
                UserRole.objects.update_or_create(user=instance, defaults={'role_id': role_id})
        return instance


class ResetPasswordSerializer(serializers.Serializer):
    newPassword = serializers.CharField(max_length=128, write_only=True)

    def validate_newPassword(self, value: str) -> str:
        if value.isdigit():
            raise serializers.ValidationError('密码不能为纯数字')
        if len(value) < 6:
            raise serializers.ValidationError('密码长度不能少于 6 位')
        password_validation.validate_password(value)
        return value


class TenantRoleSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    menuIds = serializers.PrimaryKeyRelatedField(
        source='menus', many=True, queryset=Menu.objects.all(), required=False, default=list,
    )
    permissionPointIds = serializers.PrimaryKeyRelatedField(
        source='permission_points', many=True, queryset=PermissionPoint.objects.all(), required=False, default=list,
    )

    class Meta:
        model = Role
        fields = ('id', 'name', 'code', 'description', 'isActive', 'menuIds', 'permissionPointIds', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def _clamp_to_tenant(self, attrs):
        """把菜单/权限点裁剪校验到本公司被授权范围内：越界即拒绝。"""
        tenant = _tenant_from_context(self)
        allowed_menu_ids = set(tenant.menus.values_list('id', flat=True))
        allowed_perm_ids = set(tenant.permission_points.values_list('id', flat=True))
        for menu in attrs.get('menus', []):
            if menu.id not in allowed_menu_ids:
                raise serializers.ValidationError({'menuIds': f'菜单 {menu.id} 不在本公司被授权范围内'})
        for perm in attrs.get('permission_points', []):
            if perm.id not in allowed_perm_ids:
                raise serializers.ValidationError({'permissionPointIds': f'权限点 {perm.id} 不在本公司被授权范围内'})
        return attrs

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return self._clamp_to_tenant(attrs)

    def create(self, validated_data):
        tenant = _tenant_from_context(self)
        menus = validated_data.pop('menus', [])
        perms = validated_data.pop('permission_points', [])
        role = Role.objects.create(tenant=tenant, is_template=False, **validated_data)
        role.menus.set(menus)
        role.permission_points.set(perms)
        return role

    def update(self, instance, validated_data):
        menus = validated_data.pop('menus', None)
        perms = validated_data.pop('permission_points', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if menus is not None:
            instance.menus.set(menus)
        if perms is not None:
            instance.permission_points.set(perms)
        return instance
