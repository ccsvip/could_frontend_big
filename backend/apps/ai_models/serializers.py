from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.knowledge_base.models import KnowledgeDocument
from apps.tenants.models import Tenant

from .llm_services import (
    get_effective_llm_models_for_tenant,
    llm_model_has_usage,
    mask_api_key,
    validate_llm_test_settings_values,
)
from .services.tts import get_effective_tts_config, mask_api_key as mask_tts_api_key
from .models import (
    ASRConfig,
    ASRReplacementRule,
    AgentApplication,
    ChatConversation,
    ChatMessage,
    LLMModel,
    LLMProvider,
    LLMTestSettings,
    TTSProvider,
    TTSVoice,
)


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
    providerType = serializers.CharField(source='provider_type', required=False, default='openai')
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


class TTSVoiceSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source='display_name')
    voiceCode = serializers.CharField(source='voice_code')
    avatarPath = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    isVisible = serializers.BooleanField(source='is_visible')
    sortOrder = serializers.IntegerField(source='sort_order')
    isDefault = serializers.SerializerMethodField()

    class Meta:
        model = TTSVoice
        fields = [
            'id',
            'displayName',
            'voiceCode',
            'gender',
            'avatarPath',
            'isActive',
            'isVisible',
            'sortOrder',
            'isDefault',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_isDefault(self, obj: TTSVoice) -> bool:
        default_voice_id = self.context.get('default_voice_id')
        return bool(default_voice_id and obj.id == default_voice_id)

    @extend_schema_field(serializers.CharField())
    def get_avatarPath(self, obj: TTSVoice) -> str:
        value = obj.avatar_path or ''
        request = self.context.get('request')
        if value.startswith('/') and request is not None:
            return request.build_absolute_uri(value)
        return value


class TTSVoiceWriteSerializer(serializers.ModelSerializer):
    displayName = serializers.CharField(source='display_name', required=False)
    voiceCode = serializers.CharField(source='voice_code', required=False)
    avatarPath = serializers.CharField(source='avatar_path', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    isVisible = serializers.BooleanField(source='is_visible', required=False)
    sortOrder = serializers.IntegerField(source='sort_order', required=False)

    class Meta:
        model = TTSVoice
        fields = ['displayName', 'voiceCode', 'gender', 'avatarPath', 'isActive', 'isVisible', 'sortOrder']


class PlatformTTSSettingsSerializer(serializers.ModelSerializer):
    apiKeyMasked = serializers.SerializerMethodField()
    apiKeyConfigured = serializers.SerializerMethodField()
    baseUrl = serializers.CharField(source='base_url')
    defaultVoiceId = serializers.IntegerField(source='default_voice_id', allow_null=True)
    sampleRate = serializers.IntegerField(source='sample_rate')
    defaultTestText = serializers.CharField(source='default_test_text')
    isActive = serializers.BooleanField(source='is_active')
    configured = serializers.SerializerMethodField()
    voices = serializers.SerializerMethodField()

    class Meta:
        model = TTSProvider
        fields = [
            'id',
            'code',
            'name',
            'apiKeyMasked',
            'apiKeyConfigured',
            'baseUrl',
            'model',
            'sampleRate',
            'defaultVoiceId',
            'defaultTestText',
            'isActive',
            'configured',
            'voices',
            'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_apiKeyMasked(self, obj: TTSProvider) -> str:
        return mask_tts_api_key(get_effective_tts_config(obj).api_key)

    @extend_schema_field(serializers.BooleanField())
    def get_apiKeyConfigured(self, obj: TTSProvider) -> bool:
        return bool(get_effective_tts_config(obj).api_key)

    @extend_schema_field(serializers.BooleanField())
    def get_configured(self, obj: TTSProvider) -> bool:
        config = get_effective_tts_config(obj)
        return bool(config.api_key and config.base_url and config.model and config.is_active)

    @extend_schema_field(TTSVoiceSerializer(many=True))
    def get_voices(self, obj: TTSProvider) -> list[dict]:
        return TTSVoiceSerializer(
            obj.voices.order_by('sort_order', 'id'),
            many=True,
            context={
                'default_voice_id': obj.default_voice_id,
                'request': self.context.get('request'),
            },
        ).data


class PlatformTTSSettingsWriteSerializer(serializers.ModelSerializer):
    apiKey = serializers.CharField(source='api_key', required=False, allow_blank=True, write_only=True)
    baseUrl = serializers.CharField(source='base_url', required=False, allow_blank=True, max_length=512)
    defaultVoiceId = serializers.PrimaryKeyRelatedField(
        source='default_voice',
        queryset=TTSVoice.objects.all(),
        required=False,
        allow_null=True,
    )
    sampleRate = serializers.IntegerField(source='sample_rate', required=False)
    defaultTestText = serializers.CharField(source='default_test_text', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    voices = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = TTSProvider
        fields = ['apiKey', 'baseUrl', 'model', 'sampleRate', 'defaultVoiceId', 'defaultTestText', 'isActive', 'voices']

    def validate_sampleRate(self, value: int) -> int:
        if value not in {16000, 24000}:
            raise serializers.ValidationError('采样率暂只支持 16000 或 24000')
        return value

    def validate_defaultVoiceId(self, value: TTSVoice | None) -> TTSVoice | None:
        if value is not None and self.instance is not None and value.provider_id != self.instance.id:
            raise serializers.ValidationError('默认音色不属于当前供应商')
        return value

    def update(self, instance, validated_data):
        voices = validated_data.pop('voices', None)
        if validated_data.get('api_key', None) == '':
            validated_data.pop('api_key', None)
        provider = super().update(instance, validated_data)
        if voices is not None:
            self._update_voices(provider, voices)
        return provider

    def _update_voices(self, provider: TTSProvider, voices: list[dict]) -> None:
        for item in voices:
            voice_id = item.get('id')
            if not voice_id:
                continue
            voice = provider.voices.filter(id=voice_id).first()
            if voice is None:
                continue
            serializer = TTSVoiceWriteSerializer(voice, data=item, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()


class CompanyTTSVoiceSerializer(TTSVoiceSerializer):
    class Meta(TTSVoiceSerializer.Meta):
        fields = ['id', 'displayName', 'voiceCode', 'gender', 'avatarPath', 'isDefault']


class AgentKnowledgeDocumentSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source='file_name', read_only=True)
    processingStatus = serializers.CharField(source='processing_status', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = ['id', 'title', 'fileName', 'processingStatus', 'updated_at']


class AgentApplicationSerializer(serializers.ModelSerializer):
    llmModelId = serializers.PrimaryKeyRelatedField(
        source='llm_model',
        queryset=LLMModel.objects.none(),
        required=False,
        allow_null=True,
    )
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
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
            'llmModelId',
            'llmModelName',
            'llmModelDisplayName',
            'llmProviderName',
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
        read_only_fields = (
            'id',
            'llmModelName',
            'llmModelDisplayName',
            'llmProviderName',
            'knowledgeDocuments',
            'createdBy',
            'created_at',
            'updated_at',
        )

    def get_fields(self):
        fields = super().get_fields()
        tenant = self.context.get('tenant')
        if tenant is not None:
            fields['llmModelId'].queryset = get_effective_llm_models_for_tenant(tenant)
            fields['knowledgeDocumentIds'].child_relation.queryset = KnowledgeDocument.objects.for_tenant(tenant)
        return fields

    @extend_schema_field(serializers.CharField())
    def get_llmModelName(self, obj: AgentApplication) -> str:
        return obj.llm_model.name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField())
    def get_llmModelDisplayName(self, obj: AgentApplication) -> str:
        return obj.llm_model.display_name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_llmProviderName(self, obj: AgentApplication) -> str | None:
        return obj.llm_model.provider.name if obj.llm_model and obj.llm_model.provider else None

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
    llmModelId = serializers.IntegerField(source='llm_model_id', read_only=True, allow_null=True)
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
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

    @extend_schema_field(serializers.CharField())
    def get_llmModelName(self, obj: ChatConversation) -> str:
        return obj.llm_model.name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField())
    def get_llmModelDisplayName(self, obj: ChatConversation) -> str:
        return obj.llm_model.display_name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_llmProviderName(self, obj: ChatConversation) -> str | None:
        return obj.llm_model.provider.name if obj.llm_model and obj.llm_model.provider else None

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'llmModelId', 'llmModelName',
            'llmModelDisplayName', 'llmProviderName', 'summary', 'messageCount', 'lastMessage',
            'created_at', 'updated_at',
        ]


class ChatConversationDetailSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True, allow_null=True)
    llmModelId = serializers.IntegerField(source='llm_model_id', read_only=True, allow_null=True)
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
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

    @extend_schema_field(serializers.CharField())
    def get_llmModelName(self, obj: ChatConversation) -> str:
        return obj.llm_model.name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField())
    def get_llmModelDisplayName(self, obj: ChatConversation) -> str:
        return obj.llm_model.display_name if obj.llm_model else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_llmProviderName(self, obj: ChatConversation) -> str | None:
        return obj.llm_model.provider.name if obj.llm_model and obj.llm_model.provider else None

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'llmModelId', 'llmModelName',
            'llmModelDisplayName', 'llmProviderName', 'summary', 'systemPrompt',
            'temperature', 'maxTokens', 'messages',
            'created_at', 'updated_at',
        ]


class ChatConversationConfigSerializer(serializers.Serializer):
    llmModelId = serializers.IntegerField(required=False, allow_null=True)
    systemPrompt = serializers.CharField(required=False, default='', allow_blank=True)
    temperature = serializers.FloatField(required=False, default=0.7)
    maxTokens = serializers.IntegerField(required=False, source='max_tokens', default=1000)

    def validate(self, attrs):
        system_prompt = attrs.get('systemPrompt', '')
        temperature = attrs.get('temperature', 0.7)
        max_tokens = attrs.get('max_tokens', 1000)

        if temperature < 0 or temperature > 2:
            raise serializers.ValidationError({'temperature': 'temperature 必须在 0 到 2 之间'})
        if max_tokens <= 0 or max_tokens > 320000:
            raise serializers.ValidationError({'maxTokens': 'maxTokens 必须在 1 到 320000 之间'})

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
