from typing import Any

from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import AccountApplication
from .services.permissions import build_user_access_context

User = get_user_model()


class UserRolePayloadSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    oldPassword = serializers.CharField(max_length=128, write_only=True)
    newPassword = serializers.CharField(max_length=128, write_only=True)

    def validate_oldPassword(self, value: str) -> str:
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('原密码不正确')
        return value

    def validate_newPassword(self, value: str) -> str:
        user = self.context['request'].user
        password_validation.validate_password(value, user)
        return value

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        attrs = super().validate(attrs)
        if attrs['oldPassword'] == attrs['newPassword']:
            raise serializers.ValidationError({'newPassword': '新密码不能与原密码相同'})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    menus = serializers.SerializerMethodField()
    tenant = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)
    must_change_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'role', 'permissions', 'menus', 'tenant', 'is_superuser', 'must_change_password')

    def get_display_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.username

    def _get_membership(self, obj: User):
        # 懒加载避免 app 加载顺序问题。
        from apps.tenants.services import get_user_membership
        if not hasattr(self, '_membership_cache'):
            self._membership_cache: dict[int, Any] = {}
        if obj.pk not in self._membership_cache:
            self._membership_cache[obj.pk] = get_user_membership(obj)
        return self._membership_cache[obj.pk]

    def get_tenant(self, obj: User) -> dict[str, Any] | None:
        membership = self._get_membership(obj)
        if membership is None:
            return None
        tenant = membership.tenant
        return {
            'id': tenant.id,
            'name': tenant.name,
            'code': tenant.code,
            'isTenantAdmin': membership.is_tenant_admin,
        }

    def get_must_change_password(self, obj: User) -> bool:
        membership = self._get_membership(obj)
        return bool(membership and membership.must_change_password)

    def _get_access_context(self, obj: User) -> dict[str, Any]:
        if not hasattr(self, '_access_context_cache'):
            self._access_context_cache: dict[int, dict[str, Any]] = {}

        if obj.pk not in self._access_context_cache:
            self._access_context_cache[obj.pk] = build_user_access_context(obj)

        return self._access_context_cache[obj.pk]

    @extend_schema_field(UserRolePayloadSerializer)
    def get_role(self, obj: User) -> dict[str, str] | None:
        return self._get_access_context(obj)['role']

    def get_permissions(self, obj: User) -> list[str]:
        return self._get_access_context(obj)['permissions']

    def get_menus(self, obj: User) -> list[dict[str, Any]]:
        return self._get_access_context(obj)['menus']


class AccountApplicationCreateSerializer(serializers.ModelSerializer):
    username = serializers.RegexField(
        regex=r'^[A-Za-z0-9]{3,30}$',
        max_length=30,
        error_messages={'invalid': '用户名需为 3-30 位英文字母或数字'},
    )
    applicantName = serializers.CharField(source='applicant_name', max_length=64)
    enterpriseName = serializers.CharField(source='enterprise_name', max_length=128)
    password = serializers.CharField(max_length=128, write_only=True)
    confirmPassword = serializers.CharField(max_length=128, write_only=True)

    class Meta:
        model = AccountApplication
        fields = (
            'username',
            'applicantName',
            'enterpriseName',
            'phone',
            'password',
            'confirmPassword',
            'reason',
        )

    def validate_username(self, value: str) -> str:
        username = value.strip()
        if AccountApplication.objects.filter(username=username).exists():
            raise serializers.ValidationError('该用户名已提交过申请，请更换后再提交')
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError('该用户名已存在，请更换后再提交')
        return username

    def validate_password(self, value: str) -> str:
        # 不允许纯数字，长度不少于 6 位（其余强度规则交给 AUTH_PASSWORD_VALIDATORS）。
        if value.isdigit():
            raise serializers.ValidationError('密码不能为纯数字')
        if len(value) < 6:
            raise serializers.ValidationError('密码长度不能少于 6 位')
        password_validation.validate_password(value)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        if attrs.get('password') != attrs.get('confirmPassword'):
            raise serializers.ValidationError({'confirmPassword': '两次输入的密码不一致'})
        return attrs

    def create(self, validated_data: dict[str, Any]) -> AccountApplication:
        validated_data.pop('confirmPassword', None)
        # 申请记录里只存哈希；审核通过时直接复制到 auth_user.password。
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class AccountApplicationResponseSerializer(serializers.ModelSerializer):
    applicantName = serializers.CharField(source='applicant_name')
    enterpriseName = serializers.CharField(source='enterprise_name')

    class Meta:
        model = AccountApplication
        fields = (
            'id',
            'username',
            'applicantName',
            'enterpriseName',
            'phone',
            'reason',
            'status',
            'created_at',
            'updated_at',
        )


class AccountApplicationStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=[AccountApplication.STATUS_APPROVED, AccountApplication.STATUS_REJECTED])

    class Meta:
        model = AccountApplication
        fields = ('status',)
