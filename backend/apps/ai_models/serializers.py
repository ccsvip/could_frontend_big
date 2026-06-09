from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.knowledge_base.models import KnowledgeDocument

from .models import ASRConfig, ASRReplacementRule, AgentApplication, ChatConversation, ChatMessage, LLMProvider


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
