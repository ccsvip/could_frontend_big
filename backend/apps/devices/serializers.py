from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.ai_models.services.reply_blocks import serialize_reply_blocks, text_to_blocks

from apps.ai_models.models import AgentApplication, TTSVoice
from apps.resources.models import CommandGroup, ModelAsset, Resource, ScrollingText
from apps.tenants.models import Tenant
from .services.wake_words import WakeWordEncodingError, encode_wake_word_text

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceChatLog, DeviceGroup, WakeWord


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


class AvailableTTSVoicePrimaryKeyField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return TTSVoice.objects.filter(is_active=True, is_visible=True, provider__is_active=True)


class DeviceGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceGroup
        fields = ('id', 'name', 'remark', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class DeviceApplicationSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False)
    agentApplicationId = TenantOwnedPrimaryKeyField(
        source='agent_application',
        queryset=AgentApplication.objects.all(),
        required=False,
        allow_null=True,
    )
    agentApplicationName = serializers.CharField(source='agent_application.name', read_only=True, default='')
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
    voiceToneIds = AvailableTTSVoicePrimaryKeyField(
        source='tts_voices',
        queryset=TTSVoice.objects.all(),
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
            'agentApplicationId',
            'agentApplicationName',
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
    recordId = serializers.IntegerField(source='id', read_only=True)
    deviceCode = serializers.CharField(source='code', required=False, validators=[])
    tenantId = serializers.IntegerField(source='tenant_id', read_only=True)
    tenantName = serializers.CharField(source='tenant.name', read_only=True, default='')
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
    agentApplicationId = serializers.SerializerMethodField()
    agentApplicationName = serializers.SerializerMethodField()
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
    ignoredAt = serializers.DateTimeField(source='authorization_ignored_at', read_only=True, allow_null=True)

    class Meta:
        model = Device
        fields = (
            'id',
            'recordId',
            'deviceCode',
            'name',
            'location',
            'tenantId',
            'tenantName',
            'status',
            'groupId',
            'groupName',
            'applicationId',
            'applicationName',
            'agentApplicationId',
            'agentApplicationName',
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
            'ignoredAt',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'recordId',
            'tenantId',
            'tenantName',
            'status',
            'softwareVersion',
            'systemVersion',
            'mainboardInfo',
            'registeredAt',
            'lastAuthAt',
            'lastHeartbeat',
            'ignoredAt',
            'created_at',
            'updated_at',
        )

    def get_id(self, obj: Device) -> str:
        return obj.code

    def get_agentApplicationId(self, obj: Device):
        agent_application = obj.effective_agent_application
        return agent_application.id if agent_application else None

    def get_agentApplicationName(self, obj: Device) -> str:
        agent_application = obj.effective_agent_application
        return agent_application.name if agent_application else ''

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get('code'):
            legacy_id = str(self.initial_data.get('id') or '').strip()
            if legacy_id:
                attrs['code'] = legacy_id
        if self.instance is None and not attrs.get('code'):
            raise serializers.ValidationError({'deviceCode': '设备码不能为空'})
        code = attrs.get('code')
        if code:
            duplicate_queryset = Device.objects.filter(code=code)
            if self.instance is not None:
                duplicate_queryset = duplicate_queryset.exclude(pk=self.instance.pk)
            if duplicate_queryset.exists():
                raise serializers.ValidationError({'deviceCode': '设备码已存在，不能重复绑定'})
        application = attrs.get('application')
        group = attrs.get('group')
        instance_tenant = getattr(self.instance, 'tenant', None)
        if application is not None and instance_tenant is not None and application.tenant_id != instance_tenant.id:
            raise serializers.ValidationError({'applicationId': '资源应用不属于当前设备公司'})
        if group is not None and instance_tenant is not None and group.tenant_id != instance_tenant.id:
            raise serializers.ValidationError({'groupId': '分组不属于当前设备公司'})
        if application is not None and group is not None and application.tenant_id != group.tenant_id:
            raise serializers.ValidationError({'groupId': '分组与资源应用不属于同一公司'})
        return attrs

    def create(self, validated_data):
        if not validated_data.get('registered_at'):
            validated_data['registered_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance: Device, validated_data):
        allowed = {}
        for key in ('name', 'location', 'application', 'group'):
            if key in validated_data:
                allowed[key] = validated_data[key]
        application = allowed.get('application')
        if application is not None and instance.tenant_id is None:
            allowed['tenant'] = application.tenant
        group = allowed.get('group')
        if group is not None and instance.tenant_id is None and 'tenant' not in allowed:
            allowed['tenant'] = group.tenant
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


class WakeWordDeviceSerializer(serializers.ModelSerializer):
    deviceCode = serializers.CharField(source='code', read_only=True)

    class Meta:
        model = Device
        fields = ('id', 'deviceCode', 'name', 'status')


class WakeWordSerializer(serializers.ModelSerializer):
    text = serializers.CharField(max_length=16, trim_whitespace=True)
    encodedText = serializers.CharField(source='encoded_text', read_only=True)
    keywordLine = serializers.CharField(source='keyword_line', read_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    deviceIds = serializers.PrimaryKeyRelatedField(
        source='devices',
        queryset=Device.objects.all(),
        many=True,
        required=False,
    )
    devices = WakeWordDeviceSerializer(many=True, read_only=True)
    deviceCount = serializers.IntegerField(source='devices.count', read_only=True)

    class Meta:
        model = WakeWord
        fields = (
            'id',
            'text',
            'encodedText',
            'keywordLine',
            'boost',
            'threshold',
            'isActive',
            'deviceIds',
            'devices',
            'deviceCount',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'encodedText', 'keywordLine', 'devices', 'deviceCount', 'created_at', 'updated_at')

    def validate_text(self, value: str) -> str:
        text = str(value or '').strip()
        if not text.startswith('你好'):
            raise serializers.ValidationError('唤醒词必须以“你好”开头')
        if len(text) < 4 or len(text) > 6:
            raise serializers.ValidationError('唤醒词必须为 4-6 个汉字（含“你好”）')
        if not all('\u4e00' <= char <= '\u9fff' for char in text):
            raise serializers.ValidationError('唤醒词只能包含汉字')
        return text

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = _tenant_from_context(self)
        submitted_devices = attrs.get('devices')
        if submitted_devices is not None:
            invalid = [device for device in submitted_devices if device.tenant_id != getattr(tenant, 'id', None)]
            if invalid:
                raise serializers.ValidationError({'deviceIds': '只能绑定同公司的设备'})

        text = attrs.get('text', getattr(self.instance, 'text', None))
        devices = submitted_devices
        if devices is None and self.instance is not None and 'text' in attrs:
            devices = list(self.instance.devices.all())
        if text and devices:
            queryset = WakeWord.objects.filter(tenant=tenant, text=text, devices__in=devices)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'deviceIds': '同一设备内唤醒词不能重复'})
        return attrs

    def _encode_text(self, text: str) -> str:
        try:
            return encode_wake_word_text(text)
        except WakeWordEncodingError as exc:
            raise serializers.ValidationError({'text': str(exc)}) from exc

    def create(self, validated_data):
        devices = validated_data.pop('devices', [])
        validated_data['tenant'] = _tenant_from_context(self)
        validated_data['encoded_text'] = self._encode_text(validated_data['text'])
        instance = super().create(validated_data)
        instance.devices.set(devices)
        return instance

    def update(self, instance: WakeWord, validated_data):
        devices = validated_data.pop('devices', None)
        if 'text' in validated_data and validated_data['text'] != instance.text:
            validated_data['encoded_text'] = self._encode_text(validated_data['text'])
        instance = super().update(instance, validated_data)
        if devices is not None:
            instance.devices.set(devices)
        return instance


class DeviceAuthorizationRequestSerializer(DeviceSerializer):
    bindingStatus = serializers.SerializerMethodField()
    runtimeStatus = serializers.SerializerMethodField()
    latestActivationAt = serializers.SerializerMethodField()
    latestActivationMessage = serializers.SerializerMethodField()
    latestActivationIp = serializers.SerializerMethodField()
    latestActivationDeviceInfo = serializers.SerializerMethodField()

    class Meta(DeviceSerializer.Meta):
        fields = DeviceSerializer.Meta.fields + (
            'bindingStatus',
            'runtimeStatus',
            'latestActivationAt',
            'latestActivationMessage',
            'latestActivationIp',
            'latestActivationDeviceInfo',
        )

    def _latest_activation_log(self, obj: Device):
        prefetched = getattr(obj, 'activation_logs_for_request', None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return obj.auth_logs.filter(action=DeviceAuthLog.ACTION_ACTIVATE).order_by('-created_at', '-id').first()

    def get_bindingStatus(self, obj: Device) -> str:
        if obj.authorization_ignored_at:
            return 'ignored'
        return 'bound' if obj.tenant_id else 'pending'

    def get_runtimeStatus(self, obj: Device) -> str:
        return 'ready' if obj.tenant_id and obj.effective_agent_application else 'waiting_agent'

    def get_latestActivationAt(self, obj: Device):
        log = self._latest_activation_log(obj)
        return log.created_at if log else None

    def get_latestActivationMessage(self, obj: Device) -> str:
        log = self._latest_activation_log(obj)
        return log.message if log else ''

    def get_latestActivationIp(self, obj: Device) -> str | None:
        log = self._latest_activation_log(obj)
        return log.ip_address if log else None

    def get_latestActivationDeviceInfo(self, obj: Device) -> dict:
        log = self._latest_activation_log(obj)
        return log.device_info if log else {}


class DeviceActivationLogSerializer(serializers.ModelSerializer):
    tenantId = serializers.IntegerField(source='tenant_id', read_only=True)
    tenantName = serializers.CharField(source='tenant.name', read_only=True, default='')
    applicationId = serializers.IntegerField(source='application_id', read_only=True)
    applicationName = serializers.CharField(source='application.name', read_only=True, default='')
    agentApplicationId = serializers.SerializerMethodField()
    agentApplicationName = serializers.SerializerMethodField()
    deviceName = serializers.CharField(source='device.name', read_only=True, default='')
    ipAddress = serializers.IPAddressField(source='ip_address', read_only=True, allow_null=True)
    deviceInfo = serializers.JSONField(source='device_info', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    def get_agentApplicationId(self, obj: DeviceAuthLog):
        if obj.agent_application_id is not None:
            return obj.agent_application_id
        return getattr(obj.device, 'agent_application_id', None)

    def get_agentApplicationName(self, obj: DeviceAuthLog):
        if obj.agent_application_id is not None:
            return obj.agent_application.name if obj.agent_application else ''
        agent_application = getattr(obj.device, 'agent_application', None)
        return agent_application.name if agent_application else ''

    class Meta:
        model = DeviceAuthLog
        fields = (
            'id',
            'code',
            'action',
            'result',
            'message',
            'tenantId',
            'tenantName',
            'applicationId',
            'applicationName',
            'agentApplicationId',
            'agentApplicationName',
            'deviceName',
            'ipAddress',
            'deviceInfo',
            'createdAt',
        )


class DeviceChatLogSerializer(serializers.ModelSerializer):
    tenantId = serializers.IntegerField(source='tenant_id', read_only=True)
    tenantName = serializers.CharField(source='tenant.name', read_only=True, default='')
    applicationId = serializers.IntegerField(source='application_id', read_only=True)
    applicationName = serializers.CharField(source='application.name', read_only=True, default='')
    agentApplicationId = serializers.IntegerField(source='agent_application_id', read_only=True)
    agentApplicationName = serializers.CharField(source='agent_application.name', read_only=True, default='')
    conversationId = serializers.IntegerField(source='conversation_id', read_only=True)
    deviceName = serializers.CharField(source='device.name', read_only=True, default='')
    questionText = serializers.CharField(source='question_text', read_only=True)
    answerText = serializers.CharField(source='answer_text', read_only=True)
    answerBlocks = serializers.SerializerMethodField()
    requestId = serializers.CharField(source='request_id', read_only=True)
    traceId = serializers.CharField(source='trace_id', read_only=True)
    modelName = serializers.CharField(source='model_name', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = DeviceChatLog
        fields = (
            'id',
            'code',
            'source',
            'tenantId',
            'tenantName',
            'applicationId',
            'applicationName',
            'agentApplicationId',
            'agentApplicationName',
            'conversationId',
            'deviceName',
            'questionText',
            'answerText',
            'answerBlocks',
            'requestId',
            'traceId',
            'modelName',
            'createdAt',
        )

    def get_answerBlocks(self, obj: DeviceChatLog) -> list[dict]:
        return serialize_reply_blocks(
            obj.answer_blocks or text_to_blocks(obj.answer_text),
            tenant=obj.tenant,
            request=self.context.get('request'),
        )


class DeviceBindSerializer(serializers.Serializer):
    tenantId = serializers.IntegerField()
    authorizationType = serializers.ChoiceField(
        choices=Device.AUTHORIZATION_CHOICES,
        required=False,
        default=Device.AUTHORIZATION_PERMANENT,
    )
    expiresAt = serializers.DateTimeField(required=False, allow_null=True)
    isEnabled = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        try:
            tenant = Tenant.objects.get(id=attrs['tenantId'])
        except Tenant.DoesNotExist as exc:
            raise serializers.ValidationError({'tenantId': '公司不存在'}) from exc

        if attrs.get('authorizationType') == Device.AUTHORIZATION_TRIAL and not attrs.get('expiresAt'):
            raise serializers.ValidationError({'expiresAt': '试用授权必须设置到期时间'})

        attrs['tenant'] = tenant
        return attrs

    def save(self, device: Device) -> Device:
        device.tenant = self.validated_data['tenant']
        device.authorization_ignored_at = None
        device.authorization_type = self.validated_data.get('authorizationType', Device.AUTHORIZATION_PERMANENT)
        device.expires_at = (
            self.validated_data.get('expiresAt')
            if device.authorization_type == Device.AUTHORIZATION_TRIAL
            else None
        )
        device.is_enabled = self.validated_data.get('isEnabled', True)
        device.save(update_fields=[
            'tenant',
            'authorization_ignored_at',
            'authorization_type',
            'expires_at',
            'is_enabled',
            'updated_at',
        ])
        return device


class DeviceStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    online = serializers.IntegerField()
    offline = serializers.IntegerField()
    trial = serializers.IntegerField()
    permanent = serializers.IntegerField()
