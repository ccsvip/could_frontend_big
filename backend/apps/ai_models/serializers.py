from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.knowledge_base.models import KnowledgeDocument
from apps.tenants.models import Tenant

from .llm_services import llm_model_has_usage, mask_api_key, validate_llm_test_settings_values
from .models import (
    ASRConfig,
    ASRReplacementRule,
    AgentApplication,
    ChatConversation,
    ChatMessage,
    LLMModel,
    LLMProvider,
    LLMTestSettings,
)


class LLMProviderSerializer(serializers.ModelSerializer):
    providerType = serializers.CharField(source='provider_type')
    providerTypeLabel = serializers.CharField(source='get_provider_type_display', read_only=True)
    apiBaseUrl = serializers.URLField(source='api_base_url')
    apiKey = serializers.CharField(source='api_key', required=False)
    avatarUrl = serializers.SerializerMethodField(read_only=True)
    clearAvatar = serializers.BooleanField(write_only=True, required=False, default=False)
    modelsConfig = serializers.JSONField(source='models_config', required=False, default=list)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)

    class Meta:
        model = LLMProvider
        fields = [
            'id', 'name', 'providerType', 'providerTypeLabel',
            'apiBaseUrl', 'apiKey',
            'avatar', 'avatarUrl', 'clearAvatar',
            'modelsConfig', 'isActive',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'avatar': {'write_only': True, 'required': False},
        }

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatarUrl(self, obj: LLMProvider) -> str | None:
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def validate_modelsConfig(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('模型列表必须是数组')
        for item in value:
            if not isinstance(item, dict) or 'name' not in item:
                raise serializers.ValidationError('每个模型必须包含 name 字段')
        return value

    def create(self, validated_data):
        validated_data.pop('clearAvatar', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        clear_avatar = validated_data.pop('clearAvatar', False)
        if clear_avatar and instance.avatar:
            instance.avatar.delete(save=False)
            instance.avatar = None

        if 'api_key' not in validated_data:
            validated_data.pop('api_key', None)

        return super().update(instance, validated_data)


class PlatformLLMProviderSerializer(serializers.ModelSerializer):
    providerType = serializers.CharField(source='provider_type')
    providerTypeLabel = serializers.CharField(source='get_provider_type_display', read_only=True)
    apiBaseUrl = serializers.URLField(source='api_base_url')
    apiKeyMasked = serializers.SerializerMethodField()
    apiKeyConfigured = serializers.SerializerMethodField()
    avatarUrl = serializers.SerializerMethodField(read_only=True)
    clearAvatar = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    sortOrder = serializers.IntegerField(source='sort_order')

    class Meta:
        model = LLMProvider
        fields = [
            'id', 'name', 'providerType', 'providerTypeLabel',
            'apiBaseUrl', 'apiKeyMasked', 'apiKeyConfigured',
            'avatar', 'avatarUrl', 'clearAvatar',
            'isActive', 'sortOrder', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_apiKeyMasked(self, obj: LLMProvider) -> str:
        return mask_api_key(obj.api_key)

    @extend_schema_field(serializers.BooleanField())
    def get_apiKeyConfigured(self, obj: LLMProvider) -> bool:
        return bool(obj.api_key)

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatarUrl(self, obj: LLMProvider) -> str | None:
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    @extend_schema_field(serializers.BooleanField())
    def get_clearAvatar(self, obj: LLMProvider) -> bool:
        return False


class PlatformLLMProviderWriteSerializer(serializers.ModelSerializer):
    providerType = serializers.CharField(source='provider_type')
    apiBaseUrl = serializers.URLField(source='api_base_url')
    apiKey = serializers.CharField(source='api_key', required=False, allow_blank=True, write_only=True)
    clearAvatar = serializers.BooleanField(required=False, default=False, write_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    sortOrder = serializers.IntegerField(source='sort_order', required=False, default=0)

    class Meta:
        model = LLMProvider
        fields = [
            'name', 'providerType', 'apiBaseUrl', 'apiKey',
            'avatar', 'clearAvatar', 'isActive', 'sortOrder',
        ]
        extra_kwargs = {
            'avatar': {'required': False},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get('api_key'):
            raise serializers.ValidationError({'apiKey': 'API Key 不能为空'})
        if self.instance is not None and attrs.get('api_key') == '':
            attrs.pop('api_key')
        return attrs

    def create(self, validated_data):
        validated_data.pop('clearAvatar', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        clear_avatar = validated_data.pop('clearAvatar', False)
        if clear_avatar and instance.avatar:
            instance.avatar.delete(save=False)
            instance.avatar = None
        return super().update(instance, validated_data)


class PlatformLLMModelSerializer(serializers.ModelSerializer):
    providerId = serializers.IntegerField(source='provider_id', read_only=True)
    providerName = serializers.CharField(source='provider.name', read_only=True)
    displayName = serializers.CharField(source='display_name')
    isActive = serializers.BooleanField(source='is_active')
    sortOrder = serializers.IntegerField(source='sort_order')

    class Meta:
        model = LLMModel
        fields = [
            'id', 'providerId', 'providerName', 'name', 'displayName',
            'isActive', 'sortOrder', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PlatformLLMModelWriteSerializer(serializers.ModelSerializer):
    providerId = serializers.PrimaryKeyRelatedField(
        source='provider',
        queryset=LLMProvider.objects.all(),
        required=False,
    )
    displayName = serializers.CharField(source='display_name', required=False, allow_blank=True, default='')
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    sortOrder = serializers.IntegerField(source='sort_order', required=False, default=0)

    class Meta:
        model = LLMModel
        fields = ['providerId', 'name', 'displayName', 'isActive', 'sortOrder']

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('真实模型名称不能为空')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get('provider') and not self.context.get('provider'):
            raise serializers.ValidationError({'providerId': '供应商不能为空'})
        if (
            self.instance is not None
            and 'name' in attrs
            and attrs['name'] != self.instance.name
            and llm_model_has_usage(self.instance)
        ):
            raise serializers.ValidationError({'name': '模型已被授权或使用，不能修改真实模型名称；请新增模型并停用旧模型'})
        return attrs


class LLMTestSettingsSerializer(serializers.ModelSerializer):
    testPrompt = serializers.CharField(source='test_prompt')
    testCooldownSeconds = serializers.IntegerField(source='test_cooldown_seconds')
    testTimeoutSeconds = serializers.IntegerField(source='test_timeout_seconds')
    testMaxTokens = serializers.IntegerField(source='test_max_tokens')

    class Meta:
        model = LLMTestSettings
        fields = ['testPrompt', 'testCooldownSeconds', 'testTimeoutSeconds', 'testMaxTokens', 'updated_at']
        read_only_fields = ('updated_at',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        prompt = attrs.get('test_prompt', instance.test_prompt if instance else '')
        cooldown = attrs.get('test_cooldown_seconds', instance.test_cooldown_seconds if instance else 0)
        timeout = attrs.get('test_timeout_seconds', instance.test_timeout_seconds if instance else 0)
        max_tokens = attrs.get('test_max_tokens', instance.test_max_tokens if instance else 0)
        validate_llm_test_settings_values(
            prompt=prompt,
            cooldown=cooldown,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        return attrs


class TenantLLMAuthorizationSerializer(serializers.Serializer):
    modelGrants = serializers.ListField(child=serializers.DictField(), required=True)
    defaultModelId = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        tenant_id = self.context.get('tenant_id')
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        if tenant is None:
            raise serializers.ValidationError({'tenantId': '公司不存在或已停用'})

        grants = attrs.get('modelGrants') or []
        model_ids = []
        active_model_ids = set()
        for item in grants:
            try:
                model_id = int(item.get('modelId'))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'modelGrants': 'modelId 必须是正整数'})
            if model_id <= 0:
                raise serializers.ValidationError({'modelGrants': 'modelId 必须是正整数'})
            model_ids.append(model_id)
            if bool(item.get('isActive')):
                active_model_ids.add(model_id)

        existing_ids = set(LLMModel.objects.filter(id__in=model_ids).values_list('id', flat=True))
        missing_ids = set(model_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError({'modelGrants': f'模型不存在：{min(missing_ids)}'})

        default_model_id = attrs.get('defaultModelId')
        if default_model_id is not None:
            default_model = (
                LLMModel.objects
                .select_related('provider')
                .filter(id=default_model_id)
                .first()
            )
            if default_model is None:
                raise serializers.ValidationError({'defaultModelId': '默认模型不存在'})
            if default_model_id not in active_model_ids:
                raise serializers.ValidationError({'defaultModelId': '默认模型必须包含在启用授权中'})
            if not default_model.is_active or not default_model.provider.is_active:
                raise serializers.ValidationError({'defaultModelId': '默认模型或供应商未启用'})

        attrs['tenant'] = tenant
        return attrs


class ASRConfigSerializer(serializers.ModelSerializer):
    workspaceId = serializers.CharField(source='workspace_id', required=False, allow_blank=True)
    apiKey = serializers.CharField(source='api_key', required=False, allow_blank=True, write_only=True)
    baseUrl = serializers.CharField(source='base_url', required=False, allow_blank=True, max_length=512)
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = ASRConfig
        fields = ('workspaceId', 'apiKey', 'baseUrl', 'model', 'isActive', 'updated_at')
        read_only_fields = ('updated_at',)

    def update(self, instance, validated_data):
        if validated_data.get('api_key', None) == '':
            validated_data.pop('api_key', None)
        return super().update(instance, validated_data)


class ASRReplacementRuleSerializer(serializers.ModelSerializer):
    sourceText = serializers.CharField(source='source_text', max_length=128)
    replacementText = serializers.CharField(source='replacement_text', max_length=128)
    isActive = serializers.BooleanField(source='is_active', required=False)
    tenantId = serializers.IntegerField(source='tenant_id', read_only=True)

    class Meta:
        model = ASRReplacementRule
        fields = [
            'id',
            'sourceText',
            'replacementText',
            'isActive',
            'tenantId',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ('id', 'tenantId', 'created_at', 'updated_at')

    def validate_sourceText(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('原词不能为空')
        return value

    def validate_replacementText(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('替换词不能为空')
        return value


class AgentKnowledgeDocumentSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source='file_name', read_only=True)
    processingStatus = serializers.CharField(source='processing_status', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = ['id', 'title', 'fileName', 'processingStatus', 'updated_at']


class AgentApplicationSerializer(serializers.ModelSerializer):
    llmProviderId = serializers.PrimaryKeyRelatedField(
        source='llm_provider',
        queryset=LLMProvider.objects.none(),
        required=False,
        allow_null=True,
    )
    llmProviderName = serializers.CharField(source='llm_provider.name', read_only=True, default=None)
    modelName = serializers.CharField(source='model_name', required=False, default='', allow_blank=True)
    systemPrompt = serializers.CharField(source='system_prompt', required=False, default='', allow_blank=True)
    maxTokens = serializers.IntegerField(source='max_tokens', required=False)
    knowledgeDocumentIds = serializers.PrimaryKeyRelatedField(
        source='knowledge_documents',
        queryset=KnowledgeDocument.objects.none(),
        many=True,
        required=False,
    )
    knowledgeDocuments = AgentKnowledgeDocumentSerializer(source='knowledge_documents', many=True, read_only=True)
    createdBy = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = AgentApplication
        fields = [
            'id',
            'name',
            'description',
            'llmProviderId',
            'llmProviderName',
            'modelName',
            'systemPrompt',
            'temperature',
            'maxTokens',
            'knowledgeDocumentIds',
            'knowledgeDocuments',
            'createdBy',
            'isActive',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ('id', 'llmProviderName', 'knowledgeDocuments', 'createdBy', 'created_at', 'updated_at')

    def get_fields(self):
        fields = super().get_fields()
        tenant = self.context.get('tenant')
        if tenant is not None:
            fields['llmProviderId'].queryset = LLMProvider.objects.for_tenant(tenant).filter(is_active=True)
            fields['knowledgeDocumentIds'].child_relation.queryset = KnowledgeDocument.objects.for_tenant(tenant)
        return fields

    def get_createdBy(self, obj: AgentApplication) -> str:
        if obj.created_by is None:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.username

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('应用名称不能为空')
        return value

    def validate_temperature(self, value: float) -> float:
        if value < 0 or value > 2:
            raise serializers.ValidationError('temperature 必须在 0 到 2 之间')
        return value

    def validate_maxTokens(self, value: int) -> int:
        if value <= 0 or value > 320000:
            raise serializers.ValidationError('maxTokens 必须在 1 到 320000 之间')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provider = attrs.get('llm_provider')
        model_name = attrs.get('model_name')

        if self.instance is not None:
            if provider is None and 'llm_provider' not in attrs:
                provider = self.instance.llm_provider
            if model_name is None:
                model_name = self.instance.model_name

        model_name = (model_name or '').strip()
        if 'model_name' in attrs:
            attrs['model_name'] = model_name

        if provider and model_name:
            models_config = provider.models_config or []
            model_names = {item.get('name', '').strip() for item in models_config if isinstance(item, dict)}
            if model_name not in model_names:
                raise serializers.ValidationError({'modelName': '所选模型不存在于该供应商配置中'})
        return attrs


class ChatMessageSerializer(serializers.ModelSerializer):
    conversationId = serializers.IntegerField(source='conversation_id', read_only=True)
    feedback = serializers.CharField(required=False)

    class Meta:
        model = ChatMessage
        fields = ['id', 'conversationId', 'role', 'content', 'feedback', 'created_at']
        read_only_fields = ['id', 'conversationId', 'role', 'content', 'feedback', 'created_at']


class ChatConversationListSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True, allow_null=True)
    llmProviderId = serializers.IntegerField(source='llm_provider_id', read_only=True, allow_null=True)
    llmProviderName = serializers.CharField(source='llm_provider.name', read_only=True, default=None)
    summary = serializers.CharField(read_only=True, default='')
    messageCount = serializers.SerializerMethodField()
    lastMessage = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField())
    def get_messageCount(self, obj: ChatConversation) -> int:
        return obj.messages.count()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_lastMessage(self, obj: ChatConversation) -> str | None:
        last_msg = obj.messages.order_by('-created_at').first()
        return last_msg.content[:80] if last_msg else None

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'llmProviderId', 'llmProviderName',
            'model_name', 'summary', 'messageCount', 'lastMessage',
            'created_at', 'updated_at',
        ]


class ChatConversationDetailSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True, allow_null=True)
    llmProviderId = serializers.IntegerField(source='llm_provider_id', required=False, allow_null=True)
    llmProviderName = serializers.CharField(source='llm_provider.name', read_only=True, default=None)
    modelName = serializers.CharField(source='model_name', required=False, default='')
    summary = serializers.CharField(required=False, default='')
    systemPrompt = serializers.CharField(source='system_prompt', required=False, default='')
    temperature = serializers.FloatField(required=False)
    maxTokens = serializers.IntegerField(source='max_tokens', required=False)
    messages = serializers.SerializerMethodField()

    @extend_schema_field(ChatMessageSerializer(many=True))
    def get_messages(self, obj: ChatConversation) -> list:
        # Limit to last 200 messages to avoid unbounded queries
        return ChatMessageSerializer(
            obj.messages.order_by('created_at')[:200], many=True
        ).data

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'llmProviderId', 'llmProviderName',
            'modelName', 'summary', 'systemPrompt', 'temperature', 'maxTokens', 'messages',
            'created_at', 'updated_at',
        ]


class ChatConversationConfigSerializer(serializers.Serializer):
    llmProviderId = serializers.IntegerField(required=False, allow_null=True)
    modelName = serializers.CharField(max_length=128, required=False, default='')
    systemPrompt = serializers.CharField(required=False, default='', allow_blank=True)
    temperature = serializers.FloatField(required=False, default=0.7)
    maxTokens = serializers.IntegerField(required=False, source='max_tokens', default=1000)

    def validate(self, attrs):
        provider_id = attrs.get('llmProviderId')
        model_name = attrs.get('modelName', '').strip()
        system_prompt = attrs.get('systemPrompt', '')
        temperature = attrs.get('temperature', 0.7)
        max_tokens = attrs.get('max_tokens', 1000)

        if temperature < 0 or temperature > 2:
            raise serializers.ValidationError({'temperature': 'temperature 必须在 0 到 2 之间'})
        if max_tokens <= 0 or max_tokens > 320000:
            raise serializers.ValidationError({'maxTokens': 'maxTokens 必须在 1 到 320000 之间'})

        if provider_id is None:
            attrs['modelName'] = model_name
            attrs['systemPrompt'] = system_prompt.strip()
            attrs['temperature'] = temperature
            attrs['max_tokens'] = max_tokens
            return attrs

        provider = LLMProvider.objects.filter(pk=provider_id, is_active=True).first()
        if not provider:
            raise serializers.ValidationError({'llmProviderId': '所选供应商不存在或未启用'})

        if model_name:
            models_config = provider.models_config or []
            model_names = {item.get('name', '').strip() for item in models_config if isinstance(item, dict)}
            if model_name not in model_names:
                raise serializers.ValidationError({'modelName': '所选模型不存在于该供应商配置中'})

        attrs['modelName'] = model_name
        attrs['systemPrompt'] = system_prompt.strip()
        attrs['temperature'] = temperature
        attrs['max_tokens'] = max_tokens
        return attrs


class ChatConversationCreateSerializer(ChatConversationConfigSerializer):
    title = serializers.CharField(max_length=256, required=False, default='新对话')


class ChatMessageFeedbackSerializer(serializers.Serializer):
    feedback = serializers.ChoiceField(choices=[ChatMessage.FEEDBACK_NONE, ChatMessage.FEEDBACK_UP, ChatMessage.FEEDBACK_DOWN])


class ChatSendSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, default='')
    stream = serializers.BooleanField(required=False, default=True)
    regenerateMessageId = serializers.IntegerField(required=False)
