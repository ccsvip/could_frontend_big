from django.contrib import admin

from .models import AgentApplication, ChatConversation, ChatMessage, LLMProvider, TTSProvider, TTSVoice


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'api_base_url', 'is_active', 'created_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)


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
    filter_horizontal = ('knowledge_documents',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_truncated', 'created_at')
    list_filter = ('role',)
    search_fields = ('content',)
    raw_id_fields = ('conversation',)

    @admin.display(description='内容摘要')
    def content_truncated(self, obj: ChatMessage) -> str:
        return obj.content[:80] if len(obj.content) > 80 else obj.content
