from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument
from apps.tenants.models import Tenant

from .llm_services import (
    get_effective_llm_models_for_tenant,
    llm_model_has_usage,
    mask_api_key,
    validate_llm_test_settings_values,
)
from .services.tts import get_effective_tts_config, mask_api_key as mask_tts_api_key
from .services import third_party_chatbots, tts as tts_services
from .models import (
    ASRConfig,
    AgentAnnotation,
    ASRReplacementRule,
    AgentApplication,
    ChatConversation,
    ChatMessage,
    EmbeddingModel,
    LLMModel,
    LLMProvider,
    LLMTestSettings,
    RerankModel,
    RUNTIME_BACKEND_CHOICES,
    RUNTIME_BACKEND_PLATFORM_LLM,
    RUNTIME_BACKEND_THIRD_PARTY_CHATBOT,
    THIRD_PARTY_PROVIDER_IHUAPENG,
    TenantKnowledgeModelSettings,
    TenantThirdPartyChatbotGrant,
    TenantTTSSettings,
    ThirdPartyChatbotApplication,
    ThirdPartyChatbotProvider,
    TTSProvider,
    TTSVoice,
    default_agent_opening_message,
    default_tts_session_config,
)
from .services.annotations import normalize_annotation_question
from .services.reply_blocks import blocks_to_text, normalize_reply_blocks, serialize_reply_blocks, text_to_blocks
from .services.third_party_chatbots import normalize_chatbot_api_key


def mask_knowledge_api_key(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '*' * len(value)
    return f'{value[:4]}****{value[-4:]}'


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


class PlatformThirdPartyChatbotProviderSerializer(serializers.ModelSerializer):
    providerType = serializers.CharField(source='provider_type')
    providerTypeLabel = serializers.CharField(source='get_provider_type_display', read_only=True)
    apiBaseUrl = serializers.URLField(source='api_base_url')
    apiKeyMasked = serializers.SerializerMethodField()
    apiKeyConfigured = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    sortOrder = serializers.IntegerField(source='sort_order')

    class Meta:
        model = ThirdPartyChatbotProvider
        fields = [
            'id',
            'name',
            'providerType',
            'providerTypeLabel',
            'apiBaseUrl',
            'apiKeyMasked',
            'apiKeyConfigured',
            'isActive',
            'sortOrder',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_apiKeyMasked(self, obj: ThirdPartyChatbotProvider) -> str:
        return mask_api_key(obj.api_key)

    @extend_schema_field(serializers.BooleanField())
    def get_apiKeyConfigured(self, obj: ThirdPartyChatbotProvider) -> bool:
        return bool(obj.api_key)


class PlatformThirdPartyChatbotProviderWriteSerializer(serializers.ModelSerializer):
    providerType = serializers.CharField(source='provider_type', required=False, default='ihuapeng_chatbot')
    apiBaseUrl = serializers.URLField(source='api_base_url')
    apiKey = serializers.CharField(source='api_key', required=False, allow_blank=True, write_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    sortOrder = serializers.IntegerField(source='sort_order', required=False, default=0)

    class Meta:
        model = ThirdPartyChatbotProvider
        fields = ['name', 'providerType', 'apiBaseUrl', 'apiKey', 'isActive', 'sortOrder']

    def validate_apiKey(self, value: str) -> str:
        value = normalize_chatbot_api_key(value)
        if value.lower().startswith('bearer '):
            raise serializers.ValidationError('应用密钥请直接填写原始值，不要添加 Bearer 前缀')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get('api_key'):
            raise serializers.ValidationError({'apiKey': 'API Key 不能为空'})
        if self.instance is not None and attrs.get('api_key') == '':
            attrs.pop('api_key')
        return attrs


class PlatformThirdPartyChatbotApplicationSerializer(serializers.ModelSerializer):
    providerId = serializers.IntegerField(source='provider_id', read_only=True)
    providerName = serializers.CharField(source='provider.name', read_only=True)
    providerType = serializers.CharField(source='provider.provider_type', read_only=True)
    externalApplicationId = serializers.CharField(source='external_application_id')
    isActive = serializers.BooleanField(source='is_active')
    sortOrder = serializers.IntegerField(source='sort_order')

    class Meta:
        model = ThirdPartyChatbotApplication
        fields = [
            'id',
            'providerId',
            'providerName',
            'providerType',
            'name',
            'description',
            'externalApplicationId',
            'isActive',
            'sortOrder',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class PlatformThirdPartyChatbotApplicationWriteSerializer(serializers.ModelSerializer):
    providerId = serializers.PrimaryKeyRelatedField(
        source='provider',
        queryset=ThirdPartyChatbotProvider.objects.all(),
    )
    externalApplicationId = serializers.CharField(source='external_application_id')
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    sortOrder = serializers.IntegerField(source='sort_order', required=False, default=0)

    class Meta:
        model = ThirdPartyChatbotApplication
        fields = ['providerId', 'name', 'description', 'externalApplicationId', 'isActive', 'sortOrder']

    def validate_externalApplicationId(self, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('第三方应用 ID 不能为空')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provider = attrs.get('provider') or (self.instance.provider if self.instance is not None else None)
        external_application_id = attrs.get(
            'external_application_id',
            self.instance.external_application_id if self.instance is not None else '',
        )
        if provider and provider.provider_type == THIRD_PARTY_PROVIDER_IHUAPENG:
            import uuid

            try:
                uuid.UUID(str(external_application_id))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'externalApplicationId': '华鹏第三方应用 ID 应填写文档中的 UUID，不是机器人名称或说明'})
        return attrs


class TenantThirdPartyChatbotAuthorizationSerializer(serializers.Serializer):
    chatbotGrants = serializers.ListField(child=serializers.DictField(), required=True)

    def validate(self, attrs):
        tenant_id = self.context.get('tenant_id')
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        if tenant is None:
            raise serializers.ValidationError({'tenantId': '公司不存在或已停用'})

        grants = attrs.get('chatbotGrants') or []
        chatbot_ids = []
        for item in grants:
            try:
                chatbot_id = int(item.get('chatbotId'))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'chatbotGrants': 'chatbotId 必须是正整数'})
            if chatbot_id <= 0:
                raise serializers.ValidationError({'chatbotGrants': 'chatbotId 必须是正整数'})
            chatbot_ids.append(chatbot_id)

        existing_ids = set(ThirdPartyChatbotApplication.objects.filter(id__in=chatbot_ids).values_list('id', flat=True))
        missing_ids = set(chatbot_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError({'chatbotGrants': f'第三方机器人不存在：{min(missing_ids)}'})

        attrs['tenant'] = tenant
        return attrs


class PlatformLLMModelSerializer(serializers.ModelSerializer):
    providerId = serializers.IntegerField(source='provider_id', read_only=True)
    providerName = serializers.CharField(source='provider.name', read_only=True)
    displayName = serializers.CharField(source='display_name')
    enableWebSearch = serializers.BooleanField(source='enable_web_search')
    isActive = serializers.BooleanField(source='is_active')
    sortOrder = serializers.IntegerField(source='sort_order')

    class Meta:
        model = LLMModel
        fields = [
            'id', 'providerId', 'providerName', 'name', 'displayName',
            'enableWebSearch', 'isActive', 'sortOrder', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PlatformLLMModelWriteSerializer(serializers.ModelSerializer):
    providerId = serializers.PrimaryKeyRelatedField(
        source='provider',
        queryset=LLMProvider.objects.all(),
        required=False,
    )
    displayName = serializers.CharField(source='display_name', required=False, allow_blank=True, default='')
    enableWebSearch = serializers.BooleanField(source='enable_web_search', required=False, default=False)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    sortOrder = serializers.IntegerField(source='sort_order', required=False, default=0)

    class Meta:
        model = LLMModel
        fields = ['providerId', 'name', 'displayName', 'enableWebSearch', 'isActive', 'sortOrder']

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


class KnowledgeModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    type = serializers.CharField(read_only=True)
    alias = serializers.CharField()
    model = serializers.CharField()
    baseUrl = serializers.CharField()
    apiKeyMasked = serializers.CharField(read_only=True)
    apiKeyConfigured = serializers.BooleanField(read_only=True)
    isActive = serializers.BooleanField()
    dimensions = serializers.IntegerField(required=False)
    updated_at = serializers.DateTimeField(read_only=True)


class KnowledgeModelSettingsSerializer(serializers.Serializer):
    embedding = KnowledgeModelSerializer()
    rerank = KnowledgeModelSerializer()


class KnowledgeModelSettingsWriteSerializer(serializers.Serializer):
    embedding = serializers.DictField(required=False)
    rerank = serializers.DictField(required=False)

    def _validate_model_payload(self, payload: dict, *, model_type: str) -> dict:
        allowed_fields = {'alias', 'model', 'baseUrl', 'apiKey', 'isActive', 'dimensions'}
        unknown = set(payload) - allowed_fields
        if unknown:
            raise serializers.ValidationError(f'{model_type} 包含不支持的字段：{min(unknown)}')
        result = {}
        for source, target in (('alias', 'name'), ('model', 'model'), ('baseUrl', 'base_url'), ('apiKey', 'api_key'), ('isActive', 'is_active')):
            if source in payload:
                value = payload[source]
                if source in {'alias', 'model', 'baseUrl'}:
                    value = str(value).strip()
                    if not value:
                        raise serializers.ValidationError(f'{model_type}.{source} 不能为空')
                result[target] = value
        if model_type == 'embedding' and 'dimensions' in payload:
            try:
                dimensions = int(payload['dimensions'])
            except (TypeError, ValueError):
                raise serializers.ValidationError('embedding.dimensions 必须是整数')
            if dimensions < 0:
                raise serializers.ValidationError('embedding.dimensions 不能小于 0')
            result['dimensions'] = dimensions
        return result

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalized = {}
        for model_type in ('embedding', 'rerank'):
            if model_type in attrs:
                normalized[model_type] = self._validate_model_payload(attrs[model_type], model_type=model_type)
        return normalized


class TenantKnowledgeModelSettingsSerializer(serializers.Serializer):
    embeddingModelId = serializers.IntegerField(required=False, allow_null=True)
    rerankModelId = serializers.IntegerField(required=False, allow_null=True)
    isActive = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        tenant_id = self.context.get('tenant_id')
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        if tenant is None:
            raise serializers.ValidationError({'tenantId': '公司不存在或已停用'})
        embedding_model_id = attrs.get('embeddingModelId')
        if embedding_model_id is not None and not EmbeddingModel.objects.filter(id=embedding_model_id, is_active=True).exists():
            raise serializers.ValidationError({'embeddingModelId': '嵌入模型不存在或未启用'})
        rerank_model_id = attrs.get('rerankModelId')
        if rerank_model_id is not None and not RerankModel.objects.filter(id=rerank_model_id, is_active=True).exists():
            raise serializers.ValidationError({'rerankModelId': '重排序模型不存在或未启用'})
        attrs['tenant'] = tenant
        return attrs


class ASRConfigSerializer(serializers.ModelSerializer):
    workspaceId = serializers.CharField(source='workspace_id', required=False, allow_blank=True)
    apiKey = serializers.CharField(source='api_key', required=False, allow_blank=True, write_only=True)
    baseUrl = serializers.CharField(source='base_url', required=False, allow_blank=True, max_length=512)
    vadThreshold = serializers.FloatField(source='vad_threshold', required=False, min_value=-1, max_value=1)
    vadSilenceDurationMs = serializers.IntegerField(
        source='vad_silence_duration_ms',
        required=False,
        min_value=200,
        max_value=6000,
    )
    filterFillerWords = serializers.BooleanField(source='filter_filler_words', required=False)
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = ASRConfig
        fields = (
            'workspaceId',
            'apiKey',
            'baseUrl',
            'model',
            'vadThreshold',
            'vadSilenceDurationMs',
            'filterFillerWords',
            'isActive',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

    def update(self, instance, validated_data):
        if validated_data.get('api_key', None) == '':
            validated_data.pop('api_key', None)
        return super().update(instance, validated_data)


class ASRVADConfigSerializer(serializers.ModelSerializer):
    vadThreshold = serializers.FloatField(source='vad_threshold', required=False, min_value=-1, max_value=1)
    vadSilenceDurationMs = serializers.IntegerField(
        source='vad_silence_duration_ms',
        required=False,
        min_value=200,
        max_value=6000,
    )

    class Meta:
        model = ASRConfig
        fields = ('vadThreshold', 'vadSilenceDurationMs')


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


def validate_tts_session_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise serializers.ValidationError('TTS 会话配置必须是对象')

    config = {**default_tts_session_config()}
    allowed_modes = {'server_commit', 'commit'}
    allowed_languages = {
        'Auto', 'Chinese', 'English', 'German', 'Italian', 'Portuguese',
        'Spanish', 'Japanese', 'Korean', 'French', 'Russian',
    }
    allowed_formats = {'pcm', 'wav', 'mp3', 'opus'}
    allowed_sample_rates = {8000, 16000, 24000, 48000}

    mode = str(value.get('mode', config['mode'])).strip()
    if mode not in allowed_modes:
        raise serializers.ValidationError({'mode': 'mode 只能是 server_commit 或 commit'})
    config['mode'] = mode

    language_type = str(value.get('language_type') or value.get('languageType') or config['language_type']).strip()
    if language_type not in allowed_languages:
        raise serializers.ValidationError({'languageType': 'languageType 不在支持范围内'})
    config['language_type'] = language_type

    response_format = str(value.get('response_format') or value.get('responseFormat') or config['response_format']).strip()
    if response_format not in allowed_formats:
        raise serializers.ValidationError({'responseFormat': 'responseFormat 只能是 pcm、wav、mp3 或 opus'})
    config['response_format'] = response_format

    try:
        sample_rate = int(value.get('sample_rate') or value.get('sampleRate') or config['sample_rate'])
    except (TypeError, ValueError):
        raise serializers.ValidationError({'sampleRate': 'sampleRate 必须是整数'})
    if sample_rate not in allowed_sample_rates:
        raise serializers.ValidationError({'sampleRate': 'sampleRate 只能是 8000、16000、24000 或 48000'})
    config['sample_rate'] = sample_rate

    for payload_key, stored_key, label in (
        ('speechRate', 'speech_rate', 'speechRate'),
        ('pitchRate', 'pitch_rate', 'pitchRate'),
    ):
        raw_value = value.get(stored_key, value.get(payload_key, config[stored_key]))
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            raise serializers.ValidationError({label: f'{label} 必须是数字'})
        if numeric_value < 0.5 or numeric_value > 2.0:
            raise serializers.ValidationError({label: f'{label} 必须在 0.5 到 2.0 之间'})
        config[stored_key] = round(numeric_value, 2)

    try:
        volume = int(value.get('volume', config['volume']))
    except (TypeError, ValueError):
        raise serializers.ValidationError({'volume': 'volume 必须是整数'})
    if volume < 0 or volume > 100:
        raise serializers.ValidationError({'volume': 'volume 必须在 0 到 100 之间'})
    config['volume'] = volume

    try:
        bit_rate = int(value.get('bit_rate') or value.get('bitRate') or config['bit_rate'])
    except (TypeError, ValueError):
        raise serializers.ValidationError({'bitRate': 'bitRate 必须是整数'})
    if bit_rate < 6 or bit_rate > 510:
        raise serializers.ValidationError({'bitRate': 'bitRate 必须在 6 到 510 之间'})
    config['bit_rate'] = bit_rate

    instructions = str(value.get('instructions') or '').strip()
    if len(instructions) > 4000:
        raise serializers.ValidationError({'instructions': 'instructions 不能超过 4000 个字符'})
    config['instructions'] = instructions
    config['optimize_instructions'] = bool(value.get('optimize_instructions', value.get('optimizeInstructions', config['optimize_instructions'])))
    model_code = value.get('model_code', value.get('modelCode'))
    if model_code:
        resolved_model_code = tts_services.resolve_tts_model_profile_code(str(model_code))
        if resolved_model_code != str(model_code).strip():
            raise serializers.ValidationError({'modelCode': 'TTS 模型选项不存在'})
        config['model_code'] = resolved_model_code
    return config


class PlatformTTSProviderSummarySerializer(serializers.ModelSerializer):
    defaultVoiceId = serializers.IntegerField(source='default_voice_id', allow_null=True)
    defaultVoiceName = serializers.SerializerMethodField()
    sampleRate = serializers.IntegerField(source='sample_rate')
    ttsSessionConfig = serializers.JSONField(source='tts_session_config')
    isActive = serializers.BooleanField(source='is_active')
    configured = serializers.SerializerMethodField()
    voiceCount = serializers.SerializerMethodField()

    class Meta:
        model = TTSProvider
        fields = [
            'id',
            'code',
            'name',
            'defaultVoiceId',
            'defaultVoiceName',
            'sampleRate',
            'ttsSessionConfig',
            'isActive',
            'configured',
            'voiceCount',
            'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_defaultVoiceName(self, obj: TTSProvider) -> str:
        return obj.default_voice.display_name if obj.default_voice else ''

    @extend_schema_field(serializers.BooleanField())
    def get_configured(self, obj: TTSProvider) -> bool:
        config = get_effective_tts_config(obj)
        return bool(config.api_key and config.base_url and config.model and config.is_active)

    @extend_schema_field(serializers.IntegerField())
    def get_voiceCount(self, obj: TTSProvider) -> int:
        return obj.voices.count()


class PlatformTTSSettingsSerializer(serializers.ModelSerializer):
    apiKeyMasked = serializers.SerializerMethodField()
    apiKeyConfigured = serializers.SerializerMethodField()
    baseUrl = serializers.CharField(source='base_url')
    defaultVoiceId = serializers.IntegerField(source='default_voice_id', allow_null=True)
    sampleRate = serializers.IntegerField(source='sample_rate')
    ttsSessionConfig = serializers.JSONField(source='tts_session_config')
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
            'ttsSessionConfig',
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
    ttsSessionConfig = serializers.JSONField(source='tts_session_config', required=False)
    defaultTestText = serializers.CharField(source='default_test_text', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    voices = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = TTSProvider
        fields = ['apiKey', 'baseUrl', 'model', 'sampleRate', 'ttsSessionConfig', 'defaultVoiceId', 'defaultTestText', 'isActive', 'voices']

    def validate_sampleRate(self, value: int) -> int:
        if value not in {8000, 16000, 24000, 48000}:
            raise serializers.ValidationError('采样率只支持 8000、16000、24000 或 48000')
        return value

    def validate_ttsSessionConfig(self, value: dict) -> dict:
        return validate_tts_session_config(value)

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


class CompanyTTSSettingsWriteSerializer(serializers.ModelSerializer):
    voiceId = serializers.PrimaryKeyRelatedField(
        source='default_voice',
        queryset=TTSVoice.objects.all(),
        required=False,
        allow_null=True,
    )
    ttsSessionConfig = serializers.JSONField(source='tts_session_config', required=False)
    modelCode = serializers.CharField(required=False, allow_blank=False, write_only=True)

    class Meta:
        model = TenantTTSSettings
        fields = ['voiceId', 'ttsSessionConfig', 'modelCode']

    def validate_ttsSessionConfig(self, value: dict) -> dict:
        return validate_tts_session_config(value)

    def validate_modelCode(self, value: str) -> str:
        raw = str(value or '').strip()
        resolved = tts_services.resolve_tts_model_profile_code(raw)
        if resolved != raw:
            raise serializers.ValidationError('TTS 模型选项不存在')
        return resolved

    def validate(self, attrs):
        attrs = super().validate(attrs)
        model_code = attrs.pop('modelCode', None)
        if model_code:
            session_config = dict(attrs.get('tts_session_config') or getattr(self.instance, 'tts_session_config', None) or {})
            session_config['model_code'] = model_code
            attrs['tts_session_config'] = validate_tts_session_config(session_config)
        return attrs


class AgentKnowledgeDocumentSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source='file_name', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = ['id', 'title', 'fileName', 'updated_at']


class AgentKnowledgeBaseSerializer(serializers.ModelSerializer):
    documentCount = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBase
        fields = ['id', 'name', 'description', 'documentCount', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_documentCount(self, obj: KnowledgeBase) -> int:
        return obj.documents.count()


class AgentApplicationSerializer(serializers.ModelSerializer):
    llmModelId = serializers.PrimaryKeyRelatedField(
        source='llm_model',
        queryset=LLMModel.objects.none(),
        required=False,
        allow_null=True,
    )
    runtimeBackendType = serializers.ChoiceField(
        source='runtime_backend_type',
        choices=RUNTIME_BACKEND_CHOICES,
        required=False,
        default=RUNTIME_BACKEND_PLATFORM_LLM,
    )
    thirdPartyChatbotId = serializers.PrimaryKeyRelatedField(
        source='third_party_chatbot',
        queryset=ThirdPartyChatbotApplication.objects.none(),
        required=False,
        allow_null=True,
    )
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
    thirdPartyChatbotName = serializers.SerializerMethodField()
    thirdPartyChatbotProviderName = serializers.SerializerMethodField()
    systemPrompt = serializers.CharField(source='system_prompt', required=False, default='', allow_blank=True)
    maxTokens = serializers.IntegerField(source='max_tokens', required=False)
    maxTokensUnlimited = serializers.BooleanField(source='max_tokens_unlimited', required=False)
    openingMessageEnabled = serializers.BooleanField(source='opening_message_enabled', required=False)
    openingMessage = serializers.CharField(source='opening_message', required=False, allow_blank=True, default='')
    suggestedQuestions = serializers.ListField(
        source='suggested_questions',
        child=serializers.CharField(max_length=120, allow_blank=True),
        required=False,
        allow_empty=True,
    )
    voiceInputEnabled = serializers.BooleanField(source='voice_input_enabled', required=False)
    replyPlaybackEnabled = serializers.BooleanField(source='reply_playback_enabled', required=False)
    ttsFilterPunctuation = serializers.CharField(source='tts_filter_punctuation', required=False, allow_blank=True)
    ttsFilterEmoji = serializers.BooleanField(source='tts_filter_emoji', required=False)
    knowledgeDocumentIds = serializers.PrimaryKeyRelatedField(
        source='knowledge_documents',
        queryset=KnowledgeDocument.objects.none(),
        many=True,
        required=False,
    )
    knowledgeDocuments = AgentKnowledgeDocumentSerializer(source='knowledge_documents', many=True, read_only=True)
    knowledgeBaseIds = serializers.PrimaryKeyRelatedField(
        source='knowledge_bases',
        queryset=KnowledgeBase.objects.none(),
        many=True,
        required=False,
    )
    knowledgeBases = AgentKnowledgeBaseSerializer(source='knowledge_bases', many=True, read_only=True)
    createdBy = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', required=False)
    publishedAt = serializers.DateTimeField(source='published_at', read_only=True, allow_null=True)
    publishedVersion = serializers.IntegerField(source='published_version', read_only=True)
    hasPublishedConfig = serializers.SerializerMethodField()
    isPublishedCurrent = serializers.SerializerMethodField()

    class Meta:
        model = AgentApplication
        fields = [
            'id',
            'name',
            'description',
            'runtimeBackendType',
            'llmModelId',
            'llmModelName',
            'llmModelDisplayName',
            'llmProviderName',
            'thirdPartyChatbotId',
            'thirdPartyChatbotName',
            'thirdPartyChatbotProviderName',
            'systemPrompt',
            'temperature',
            'maxTokens',
            'maxTokensUnlimited',
            'openingMessageEnabled',
            'openingMessage',
            'suggestedQuestions',
            'voiceInputEnabled',
            'replyPlaybackEnabled',
            'ttsFilterPunctuation',
            'ttsFilterEmoji',
            'knowledgeDocumentIds',
            'knowledgeDocuments',
            'knowledgeBaseIds',
            'knowledgeBases',
            'createdBy',
            'isActive',
            'publishedAt',
            'publishedVersion',
            'hasPublishedConfig',
            'isPublishedCurrent',
            'created_at',
            'updated_at',
        ]
        read_only_fields = (
            'id',
            'llmModelName',
            'llmModelDisplayName',
            'llmProviderName',
            'thirdPartyChatbotName',
            'thirdPartyChatbotProviderName',
            'knowledgeDocuments',
            'knowledgeBases',
            'createdBy',
            'publishedAt',
            'publishedVersion',
            'hasPublishedConfig',
            'isPublishedCurrent',
            'created_at',
            'updated_at',
        )

    def get_fields(self):
        fields = super().get_fields()
        tenant = self.context.get('tenant')
        if tenant is not None:
            fields['llmModelId'].queryset = get_effective_llm_models_for_tenant(tenant)
            fields['thirdPartyChatbotId'].queryset = ThirdPartyChatbotApplication.objects.select_related('provider').all()
            fields['knowledgeDocumentIds'].child_relation.queryset = KnowledgeDocument.objects.for_tenant(tenant)
            fields['knowledgeBaseIds'].child_relation.queryset = KnowledgeBase.objects.for_tenant(tenant).filter(is_active=True)
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

    @extend_schema_field(serializers.CharField())
    def get_thirdPartyChatbotName(self, obj: AgentApplication) -> str:
        return obj.third_party_chatbot.name if obj.third_party_chatbot else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_thirdPartyChatbotProviderName(self, obj: AgentApplication) -> str | None:
        if obj.third_party_chatbot and obj.third_party_chatbot.provider:
            return obj.third_party_chatbot.provider.name
        return None

    def get_createdBy(self, obj: AgentApplication) -> str:
        if obj.created_by is None:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.username

    @extend_schema_field(serializers.BooleanField())
    def get_hasPublishedConfig(self, obj: AgentApplication) -> bool:
        return bool(obj.published_at and obj.published_config)

    @extend_schema_field(serializers.BooleanField())
    def get_isPublishedCurrent(self, obj: AgentApplication) -> bool:
        return obj.is_published_current

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('应用名称不能为空')
        tenant = self.context.get('tenant')
        if tenant is not None:
            queryset = AgentApplication.objects.filter(tenant=tenant, name=value)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError('同名智能体已存在，请更换名称')
        return value

    def validate_temperature(self, value: float) -> float:
        if value < 0 or value > 2:
            raise serializers.ValidationError('temperature 必须在 0 到 2 之间')
        return value

    def validate_maxTokens(self, value: int) -> int:
        if value <= 0 or value > 320000:
            raise serializers.ValidationError('maxTokens 必须在 1 到 320000 之间')
        return value

    def validate_openingMessage(self, value: str) -> str:
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError('开场白不能超过 200 字')
        return value

    def validate_suggestedQuestions(self, value: list[str]) -> list[str]:
        if len(value) > 10:
            raise serializers.ValidationError('suggestedQuestions 建议问题最多 10 条')
        normalized = []
        for item in value:
            text = str(item).strip()
            if not text:
                raise serializers.ValidationError('suggestedQuestions 建议问题不能为空')
            if len(text) > 120:
                raise serializers.ValidationError('suggestedQuestions 单条建议问题不能超过 120 字')
            normalized.append(text)
        return normalized

    def validate_ttsFilterPunctuation(self, value: str) -> str:
        value = ''.join(dict.fromkeys(str(value).strip()))
        if len(value) > 64:
            raise serializers.ValidationError('TTS 过滤标点不能超过 64 个字符')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = self.context.get('tenant')
        runtime_backend_type = attrs.get(
            'runtime_backend_type',
            self.instance.runtime_backend_type if self.instance is not None else RUNTIME_BACKEND_PLATFORM_LLM,
        )
        third_party_chatbot = attrs.get(
            'third_party_chatbot',
            self.instance.third_party_chatbot if self.instance is not None else None,
        )
        if third_party_chatbot is not None and not third_party_chatbots.is_chatbot_effective_for_tenant(tenant, third_party_chatbot):
            raise serializers.ValidationError({'thirdPartyChatbotId': '第三方会话机器人未授权给当前公司'})
        if runtime_backend_type == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
            if third_party_chatbot is None:
                raise serializers.ValidationError({'thirdPartyChatbotId': '请选择第三方会话机器人'})
        return attrs

    def create(self, validated_data):
        if not validated_data.get('opening_message'):
            validated_data['opening_message'] = default_agent_opening_message(validated_data.get('name', ''))
        return super().create(validated_data)


class AgentAnnotationSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True)
    sourceMessageId = serializers.IntegerField(source='source_message_id', read_only=True, allow_null=True)
    answerBlocks = serializers.JSONField(source='answer_blocks', required=False)
    isActive = serializers.BooleanField(source='is_active', required=False)
    hitCount = serializers.IntegerField(source='hit_count', read_only=True)
    lastHitAt = serializers.DateTimeField(source='last_hit_at', read_only=True, allow_null=True)
    createdBy = serializers.SerializerMethodField()

    class Meta:
        model = AgentAnnotation
        fields = [
            'id',
            'applicationId',
            'question',
            'answer',
            'answerBlocks',
            'sourceMessageId',
            'isActive',
            'hitCount',
            'lastHitAt',
            'createdBy',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'applicationId',
            'sourceMessageId',
            'hitCount',
            'lastHitAt',
            'createdBy',
            'created_at',
            'updated_at',
        ]

    def get_createdBy(self, obj: AgentAnnotation) -> str:
        if obj.created_by is None:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.username

    def validate_question(self, value: str) -> str:
        value = normalize_annotation_question(value)
        if not value:
            raise serializers.ValidationError('问题不能为空')
        return value

    def validate_answer(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('答案不能为空')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = self.context.get('tenant')
        fallback_text = attrs.get('answer')
        if fallback_text is None and self.instance is not None:
            fallback_text = self.instance.answer
        raw_blocks = attrs.get('answer_blocks')
        if raw_blocks is None and 'answer' in attrs:
            raw_blocks = text_to_blocks(attrs.get('answer') or '')
        if raw_blocks is not None:
            try:
                blocks = normalize_reply_blocks(raw_blocks, fallback_text=fallback_text or '', tenant=tenant)
            except ValueError as exc:
                raise serializers.ValidationError({'answerBlocks': str(exc)}) from exc
            if not blocks:
                raise serializers.ValidationError({'answerBlocks': '标准回复不能为空'})
            attrs['answer_blocks'] = blocks
            attrs['answer'] = blocks_to_text(blocks)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['answerBlocks'] = serialize_reply_blocks(
            instance.answer_blocks or text_to_blocks(instance.answer),
            tenant=instance.tenant,
            request=self.context.get('request'),
        )
        return data


class AgentAnnotationCreateFromMessageSerializer(serializers.Serializer):
    messageId = serializers.IntegerField()
    question = serializers.CharField(max_length=500)
    answer = serializers.CharField()
    answerBlocks = serializers.JSONField(required=False)

    def validate_question(self, value: str) -> str:
        value = normalize_annotation_question(value)
        if not value:
            raise serializers.ValidationError('问题不能为空')
        return value

    def validate_answer(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('答案不能为空')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        raw_blocks = attrs.get('answerBlocks') or text_to_blocks(attrs.get('answer') or '')
        try:
            blocks = normalize_reply_blocks(raw_blocks, fallback_text=attrs.get('answer') or '', tenant=self.context.get('tenant'))
        except ValueError as exc:
            raise serializers.ValidationError({'answerBlocks': str(exc)}) from exc
        attrs['answerBlocks'] = blocks
        attrs['answer'] = blocks_to_text(blocks)
        return attrs


class ChatMessageSerializer(serializers.ModelSerializer):
    conversationId = serializers.IntegerField(source='conversation_id', read_only=True)
    contentBlocks = serializers.SerializerMethodField()
    feedback = serializers.CharField(required=False)

    class Meta:
        model = ChatMessage
        fields = ['id', 'conversationId', 'role', 'content', 'contentBlocks', 'feedback', 'created_at']
        read_only_fields = ['id', 'conversationId', 'role', 'content', 'contentBlocks', 'feedback', 'created_at']

    def get_contentBlocks(self, obj: ChatMessage) -> list[dict]:
        return serialize_reply_blocks(
            obj.content_blocks or text_to_blocks(obj.content),
            tenant=obj.conversation.tenant,
            request=self.context.get('request'),
        )


class ChatConversationListSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True, allow_null=True)
    runtimeBackendType = serializers.CharField(source='runtime_backend_type', read_only=True)
    llmModelId = serializers.IntegerField(source='llm_model_id', read_only=True, allow_null=True)
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
    thirdPartyChatbotId = serializers.IntegerField(source='third_party_chatbot_id', read_only=True, allow_null=True)
    thirdPartyChatbotName = serializers.SerializerMethodField()
    thirdPartyChatbotProviderName = serializers.SerializerMethodField()
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

    @extend_schema_field(serializers.CharField())
    def get_thirdPartyChatbotName(self, obj: ChatConversation) -> str:
        return obj.third_party_chatbot.name if obj.third_party_chatbot else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_thirdPartyChatbotProviderName(self, obj: ChatConversation) -> str | None:
        if obj.third_party_chatbot and obj.third_party_chatbot.provider:
            return obj.third_party_chatbot.provider.name
        return None

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'runtimeBackendType', 'llmModelId', 'llmModelName',
            'llmModelDisplayName', 'llmProviderName', 'thirdPartyChatbotId', 'thirdPartyChatbotName',
            'thirdPartyChatbotProviderName', 'summary', 'messageCount', 'lastMessage',
            'created_at', 'updated_at',
        ]


class ChatConversationDetailSerializer(serializers.ModelSerializer):
    applicationId = serializers.IntegerField(source='application_id', read_only=True, allow_null=True)
    runtimeBackendType = serializers.CharField(source='runtime_backend_type', read_only=True)
    llmModelId = serializers.IntegerField(source='llm_model_id', read_only=True, allow_null=True)
    llmModelName = serializers.SerializerMethodField()
    llmModelDisplayName = serializers.SerializerMethodField()
    llmProviderName = serializers.SerializerMethodField()
    thirdPartyChatbotId = serializers.IntegerField(source='third_party_chatbot_id', read_only=True, allow_null=True)
    thirdPartyChatbotName = serializers.SerializerMethodField()
    thirdPartyChatbotProviderName = serializers.SerializerMethodField()
    summary = serializers.CharField(required=False, default='')
    systemPrompt = serializers.CharField(source='system_prompt', required=False, default='')
    temperature = serializers.FloatField(required=False)
    maxTokens = serializers.IntegerField(source='max_tokens', required=False)
    maxTokensUnlimited = serializers.BooleanField(source='max_tokens_unlimited', required=False)
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

    @extend_schema_field(serializers.CharField())
    def get_thirdPartyChatbotName(self, obj: ChatConversation) -> str:
        return obj.third_party_chatbot.name if obj.third_party_chatbot else ''

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_thirdPartyChatbotProviderName(self, obj: ChatConversation) -> str | None:
        if obj.third_party_chatbot and obj.third_party_chatbot.provider:
            return obj.third_party_chatbot.provider.name
        return None

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'applicationId', 'runtimeBackendType', 'llmModelId', 'llmModelName',
            'llmModelDisplayName', 'llmProviderName', 'thirdPartyChatbotId', 'thirdPartyChatbotName',
            'thirdPartyChatbotProviderName', 'summary', 'systemPrompt',
            'temperature', 'maxTokens', 'maxTokensUnlimited', 'messages',
            'created_at', 'updated_at',
        ]


class ChatConversationConfigSerializer(serializers.Serializer):
    runtimeBackendType = serializers.ChoiceField(
        source='runtime_backend_type',
        choices=[RUNTIME_BACKEND_PLATFORM_LLM, RUNTIME_BACKEND_THIRD_PARTY_CHATBOT],
        required=False,
    )
    llmModelId = serializers.IntegerField(required=False, allow_null=True)
    thirdPartyChatbotId = serializers.IntegerField(required=False, allow_null=True)
    systemPrompt = serializers.CharField(required=False, default='', allow_blank=True)
    temperature = serializers.FloatField(required=False, default=0.7)
    maxTokens = serializers.IntegerField(required=False, source='max_tokens', default=1000)
    maxTokensUnlimited = serializers.BooleanField(required=False, source='max_tokens_unlimited', default=False)

    def validate(self, attrs):
        system_prompt = attrs.get('systemPrompt', '')
        temperature = attrs.get('temperature', 0.7)
        max_tokens = attrs.get('max_tokens', 1000)
        max_tokens_unlimited = attrs.get('max_tokens_unlimited', False)

        if temperature < 0 or temperature > 2:
            raise serializers.ValidationError({'temperature': 'temperature 必须在 0 到 2 之间'})
        if not max_tokens_unlimited and (max_tokens <= 0 or max_tokens > 320000):
            raise serializers.ValidationError({'maxTokens': 'maxTokens 必须在 1 到 320000 之间'})

        attrs['systemPrompt'] = system_prompt.strip()
        attrs['temperature'] = temperature
        attrs['max_tokens'] = max_tokens
        attrs['max_tokens_unlimited'] = max_tokens_unlimited
        return attrs


class ChatConversationCreateSerializer(ChatConversationConfigSerializer):
    title = serializers.CharField(max_length=256, required=False, default='新对话')


class ChatMessageFeedbackSerializer(serializers.Serializer):
    feedback = serializers.ChoiceField(choices=[ChatMessage.FEEDBACK_NONE, ChatMessage.FEEDBACK_UP, ChatMessage.FEEDBACK_DOWN])


class ChatSendSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, default='')
    stream = serializers.BooleanField(required=False, default=True)
    regenerateMessageId = serializers.IntegerField(required=False)
