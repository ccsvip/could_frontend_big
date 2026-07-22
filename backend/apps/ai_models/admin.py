from django.contrib import admin

from .models import (
    AgentAnnotation,
    AgentApplication,
    BailianKnowledgeConfig,
    ChatConversation,
    ChatMessage,
    EmbeddingModel,
    LLMProvider,
    RerankModel,
    TenantKnowledgeModelSettings,
    TTSProvider,
    TTSVoice,
)


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'api_base_url', 'is_active', 'created_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)


@admin.register(EmbeddingModel)
class EmbeddingModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'model', 'dimensions', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'model')


@admin.register(RerankModel)
class RerankModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'model', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'model')


@admin.register(BailianKnowledgeConfig)
class BailianKnowledgeConfigAdmin(admin.ModelAdmin):
    list_display = ('workspace_id', 'endpoint', 'is_active', 'updated_at')
    readonly_fields = ('access_key_secret_encrypted', 'updated_at')
    exclude = ('access_key_secret_encrypted',)


@admin.register(TenantKnowledgeModelSettings)
class TenantKnowledgeModelSettingsAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'managed_rag_enabled', 'bailian_category_id', 'embedding_model', 'rerank_model', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    raw_id_fields = ('tenant', 'embedding_model', 'rerank_model')


@admin.register(TTSProvider)
class TTSProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'model', 'sample_rate', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'model')
    raw_id_fields = ('default_voice',)


@admin.register(TTSVoice)
class TTSVoiceAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'voice_code', 'provider', 'gender', 'is_active', 'is_visible', 'sort_order')
    list_filter = ('provider', 'gender', 'is_active', 'is_visible')
    search_fields = ('display_name', 'voice_code')


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'application', 'llm_provider', 'model_name', 'created_at', 'updated_at')
    list_filter = ('application', 'llm_provider')
    search_fields = ('title', 'user__username')
    raw_id_fields = ('user', 'application', 'llm_provider')


@admin.register(AgentApplication)
class AgentApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'llm_provider', 'model_name', 'is_active', 'created_by', 'created_at', 'updated_at')
    list_filter = ('is_active', 'llm_provider')
    search_fields = ('name', 'description', 'system_prompt')
    raw_id_fields = ('llm_provider', 'created_by', 'tenant')
    filter_horizontal = ('knowledge_documents', 'knowledge_bases')


@admin.register(AgentAnnotation)
class AgentAnnotationAdmin(admin.ModelAdmin):
    list_display = ('application', 'question', 'is_active', 'hit_count', 'last_hit_at', 'updated_at')
    list_filter = ('is_active', 'application')
    search_fields = ('question', 'answer', 'application__name')
    raw_id_fields = ('application', 'tenant', 'source_message', 'created_by')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_truncated', 'created_at')
    list_filter = ('role',)
    search_fields = ('content',)
    raw_id_fields = ('conversation',)

    @admin.display(description='内容摘要')
    def content_truncated(self, obj: ChatMessage) -> str:
        return obj.content[:80] if len(obj.content) > 80 else obj.content
