from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    ASRDeviceStatusView,
    ASRSettingsTestView,
    ASRSettingsView,
    ASRStatusView,
    ASRTestView,
    ASRReplacementRuleViewSet,
    AgentApplicationViewSet,
    ChatConversationViewSet,
    LLMTestSettingsView,
    LLMProviderViewSet,
    PlatformLLMModelViewSet,
    PlatformLLMProviderModelsView,
    PlatformLLMProviderViewSet,
    TenantLLMAuthorizationView,
)

router = DefaultRouter()
router.register('settings/llm/providers', PlatformLLMProviderViewSet, basename='platform-llm-provider')
router.register('settings/llm/models', PlatformLLMModelViewSet, basename='platform-llm-model')
router.register('ai-models/llm-providers', LLMProviderViewSet, basename='llm-provider')
router.register('ai-models/asr/replacement-rules', ASRReplacementRuleViewSet, basename='asr-replacement-rule')
router.register('ai-models/applications', AgentApplicationViewSet, basename='agent-application')
router.register('ai-models/chat/conversations', ChatConversationViewSet, basename='chat-conversation')

urlpatterns = [
    path('settings/asr/', ASRSettingsView.as_view(), name='asr-settings'),
    path('settings/asr/test/', ASRSettingsTestView.as_view(), name='asr-settings-test'),
    path('settings/llm/providers/<int:provider_id>/models/', PlatformLLMProviderModelsView.as_view(), name='platform-llm-provider-models'),
    path('settings/llm/test-settings/', LLMTestSettingsView.as_view(), name='platform-llm-test-settings'),
    path('settings/llm/tenants/<int:tenant_id>/authorization/', TenantLLMAuthorizationView.as_view(), name='platform-llm-tenant-authorization'),
    path('ai-models/asr/status/', ASRStatusView.as_view(), name='asr-status'),
    path('ai-models/asr/device-status/', ASRDeviceStatusView.as_view(), name='asr-device-status'),
    path('ai-models/asr/test/', ASRTestView.as_view(), name='asr-test'),
] + router.urls
