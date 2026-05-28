from django.contrib import admin

from .models import ChatConversation, ChatMessage, LLMProvider


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'api_base_url', 'is_active', 'created_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'llm_provider', 'model_name', 'created_at', 'updated_at')
    list_filter = ('llm_provider',)
    search_fields = ('title', 'user__username')
    raw_id_fields = ('user', 'llm_provider')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_truncated', 'created_at')
    list_filter = ('role',)
    search_fields = ('content',)
    raw_id_fields = ('conversation',)

    @admin.display(description='内容摘要')
    def content_truncated(self, obj: ChatMessage) -> str:
        return obj.content[:80] if len(obj.content) > 80 else obj.content
