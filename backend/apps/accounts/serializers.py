from typing import Any

from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
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

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'role', 'permissions', 'menus')

    def get_display_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.username

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
        regex=r'^[A-Za-z0-9_.-]{3,30}$',
        max_length=30,
        error_messages={'invalid': '用户名需为 3-30 位字母、数字、下划线、点或短横线'},
    )
    applicantName = serializers.CharField(source='applicant_name', max_length=64)

    class Meta:
        model = AccountApplication
        fields = ('username', 'applicantName', 'phone', 'email', 'reason')

    def validate_username(self, value: str) -> str:
        username = value.strip()
        if AccountApplication.objects.filter(username=username).exists():
            raise serializers.ValidationError('该用户名已提交过申请，请更换后再提交')
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError('该用户名已存在，请更换后再提交')
        return username


class AccountApplicationResponseSerializer(serializers.ModelSerializer):
    applicantName = serializers.CharField(source='applicant_name')

    class Meta:
        model = AccountApplication
        fields = ('id', 'username', 'applicantName', 'phone', 'email', 'reason', 'status', 'created_at', 'updated_at')


class AccountApplicationStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=[AccountApplication.STATUS_APPROVED, AccountApplication.STATUS_REJECTED])

    class Meta:
        model = AccountApplication
        fields = ('status',)
