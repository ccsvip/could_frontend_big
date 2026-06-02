from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.resources.models import CommandGroup, ModelAsset, Resource, ScrollingText, VoiceTone

from .models import Device, DeviceApplication, DeviceAuthorizationCode, DeviceGroup


def _tenant_from_context(serializer: serializers.Serializer):
    view = serializer.context.get('view')
    if view and hasattr(view, 'request_tenant'):
        return view.request_tenant
    request = serializer.context.get('request')
    user = getattr(request, 'user', None)
    return getattr(getattr(user, 'membership', None), 'tenant', None)


class TenantOwnedPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = _tenant_from_context(self.root)
        user = getattr(getattr(self.root.context.get('request'), 'user', None), 'is_superuser', False)
        if user:
            return queryset
        if tenant is None:
            return queryset.none()
        return queryset.for_tenant(tenant)


class DeviceGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceGroup
        fields = ('id', 'name', 'remark', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class DeviceApplicationSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False)
    resourceIds = TenantOwnedPrimaryKeyField(
        source='resources',
        queryset=Resource.objects.all(),
        many=True,
        required=False,
    )
    scrollingTextIds = TenantOwnedPrimaryKeyField(
        source='scrolling_texts',
        queryset=ScrollingText.objects.all(),
        many=True,
        required=False,
    )
    voiceToneIds = TenantOwnedPrimaryKeyField(
        source='voice_tones',
        queryset=VoiceTone.objects.all(),
        many=True,
        required=False,
    )
    modelAssetIds = TenantOwnedPrimaryKeyField(
        source='model_assets',
        queryset=ModelAsset.objects.all(),
        many=True,
        required=False,
    )
    commandGroupIds = TenantOwnedPrimaryKeyField(
        source='command_groups',
        queryset=CommandGroup.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = DeviceApplication
        fields = (
            'id',
            'name',
            'code',
            'description',
            'isActive',
            'resourceIds',
            'scrollingTextIds',
            'voiceToneIds',
            'modelAssetIds',
            'commandGroupIds',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class DeviceSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    deviceCode = serializers.CharField(source='code', required=False)
    groupId = TenantOwnedPrimaryKeyField(
        source='group',
        queryset=DeviceGroup.objects.all(),
        required=False,
        allow_null=True,
    )
    groupName = serializers.CharField(source='group.name', read_only=True, default='')
    applicationId = TenantOwnedPrimaryKeyField(
        source='application',
        queryset=DeviceApplication.objects.all(),
        required=False,
        allow_null=True,
    )
    applicationName = serializers.CharField(source='application.name', read_only=True, default='')
    authorizationType = serializers.ChoiceField(
        source='authorization_type',
        choices=Device.AUTHORIZATION_CHOICES,
        required=False,
    )
    authorizationTypeLabel = serializers.CharField(source='get_authorization_type_display', read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', required=False, allow_null=True)
    softwareVersion = serializers.CharField(source='software_version', read_only=True)
    systemVersion = serializers.CharField(source='system_version', read_only=True)
    mainboardInfo = serializers.CharField(source='mainboard_info', read_only=True)
    isEnabled = serializers.BooleanField(source='is_enabled', required=False)
    registeredAt = serializers.DateTimeField(source='registered_at', read_only=True, allow_null=True)
    lastAuthAt = serializers.DateTimeField(source='last_auth_at', read_only=True, allow_null=True)
    lastHeartbeat = serializers.DateTimeField(source='last_heartbeat', read_only=True, allow_null=True)

    class Meta:
        model = Device
        fields = (
            'id',
            'deviceCode',
            'name',
            'location',
            'status',
            'groupId',
            'groupName',
            'applicationId',
            'applicationName',
            'authorizationType',
            'authorizationTypeLabel',
            'expiresAt',
            'softwareVersion',
            'systemVersion',
            'mainboardInfo',
            'isEnabled',
            'registeredAt',
            'lastAuthAt',
            'lastHeartbeat',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'status',
            'softwareVersion',
            'systemVersion',
            'mainboardInfo',
            'registeredAt',
            'lastAuthAt',
            'lastHeartbeat',
            'created_at',
            'updated_at',
        )

    def get_id(self, obj: Device) -> str:
        return obj.code

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get('code'):
            legacy_id = str(self.initial_data.get('id') or '').strip()
            if legacy_id:
                attrs['code'] = legacy_id
        if self.instance is None and not attrs.get('code'):
            raise serializers.ValidationError({'deviceCode': '设备码不能为空'})
        return attrs

    def create(self, validated_data):
        if not validated_data.get('registered_at'):
            validated_data['registered_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance: Device, validated_data):
        allowed = {}
        for key in ('name', 'group', 'is_enabled', 'authorization_type', 'expires_at'):
            if key in validated_data:
                allowed[key] = validated_data[key]
        return super().update(instance, allowed)


class DeviceDetailSerializer(DeviceSerializer):
    deviceInfo = serializers.JSONField(source='device_info', read_only=True)

    class Meta(DeviceSerializer.Meta):
        fields = DeviceSerializer.Meta.fields + ('deviceInfo',)


class DeviceAuthorizationCodeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        max_length=64,
        trim_whitespace=True,
        error_messages={'required': '请输入授权码', 'blank': '请输入授权码'},
    )
    applicationId = TenantOwnedPrimaryKeyField(source='application', queryset=DeviceApplication.objects.all())
    applicationName = serializers.CharField(source='application.name', read_only=True)
    authorizationType = serializers.ChoiceField(
        source='authorization_type',
        choices=Device.AUTHORIZATION_CHOICES,
        required=False,
    )
    authorizationTypeLabel = serializers.CharField(source='get_authorization_type_display', read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', required=False, allow_null=True)
    usedAt = serializers.DateTimeField(source='used_at', read_only=True, allow_null=True)
    usedDeviceCode = serializers.CharField(source='used_by_device.code', read_only=True, default='')

    class Meta:
        model = DeviceAuthorizationCode
        fields = (
            'id',
            'code',
            'status',
            'applicationId',
            'applicationName',
            'authorizationType',
            'authorizationTypeLabel',
            'expiresAt',
            'usedAt',
            'usedDeviceCode',
            'remark',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'status', 'usedAt', 'usedDeviceCode', 'created_at', 'updated_at')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('authorization_type') == Device.AUTHORIZATION_TRIAL and not attrs.get('expires_at'):
            raise serializers.ValidationError({'expiresAt': '试用授权必须设置到期时间'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)

class DeviceStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    online = serializers.IntegerField()
    offline = serializers.IntegerField()
    trial = serializers.IntegerField()
    permanent = serializers.IntegerField()
