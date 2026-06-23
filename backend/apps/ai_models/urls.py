from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    ASRDeviceStatusView,
    ASRConfigView,
    ASRSettingsTestView,
    ASRSettingsView,
    ASRStatusView,
    ASRTestView,
    ASRReplacementRuleViewSet,
    AgentApplicationViewSet,
    ChatConversationViewSet,
    CompanyTTSDefaultVoiceView,
    CompanyTTSTestView,
    CompanyTTSOptionsView,
    CompanyLLMDefaultModelView,
    CompanyLLMModelTestView,
    CompanyLLMOptionsView,
    PlatformKnowledgeModelSettingsView,
    LLMTestSettingsView,
    PlatformLLMModelViewSet,
    PlatformLLMProviderModelsView,
    PlatformLLMProviderViewSet,
    TenantLLMAuthorizationView,
    TenantKnowledgeModelAuthorizationView,
    TTSRuntimeView,
    TTSProviderListView,
    TTSSettingsTestView,
    TTSSettingsView,
)

router = DefaultRouter()
router.register('settings/llm/providers', PlatformLLMProviderViewSet, basename='platform-llm-provider')
router.register('settings/llm/models', PlatformLLMModelViewSet, basename='platform-llm-model')
router.register('ai-models/asr/replacement-rules', ASRReplacementRuleViewSet, basename='asr-replacement-rule')
router.register('ai-models/applications', AgentApplicationViewSet, basename='agent-application')
router.register('ai-models/chat/conversations', ChatConversationViewSet, basename='chat-conversation')

urlpatterns = [
    path('settings/asr/', ASRSettingsView.as_view(), name='asr-settings'),
    path('settings/asr/test/', ASRSettingsTestView.as_view(), name='asr-settings-test'),
    path('settings/tts/providers/', TTSProviderListView.as_view(), name='tts-provider-list'),
    path('settings/tts/providers/<slug:provider_code>/', TTSSettingsView.as_view(), name='tts-provider-settings'),
    path('settings/tts/providers/<slug:provider_code>/test/', TTSSettingsTestView.as_view(), name='tts-provider-settings-test'),
    path('settings/tts/', TTSSettingsView.as_view(), name='tts-settings'),
    path('settings/tts/test/', TTSSettingsTestView.as_view(), name='tts-settings-test'),
    path('settings/llm/providers/<int:provider_id>/models/', PlatformLLMProviderModelsView.as_view(), name='platform-llm-provider-models'),
    path('settings/llm/test-settings/', LLMTestSettingsView.as_view(), name='platform-llm-test-settings'),
    path('settings/llm/tenants/<int:tenant_id>/authorization/', TenantLLMAuthorizationView.as_view(), name='platform-llm-tenant-authorization'),
    path('settings/knowledge-base/models/', PlatformKnowledgeModelSettingsView.as_view(), name='platform-knowledge-model-settings'),
    path('settings/knowledge-base/tenants/<int:tenant_id>/authorization/', TenantKnowledgeModelAuthorizationView.as_view(), name='platform-knowledge-tenant-authorization'),
    path('ai-models/llm/options/', CompanyLLMOptionsView.as_view(), name='company-llm-options'),
    path('ai-models/llm/default-model/', CompanyLLMDefaultModelView.as_view(), name='company-llm-default-model'),
    path('ai-models/llm/models/<int:model_id>/test/', CompanyLLMModelTestView.as_view(), name='company-llm-model-test'),
    path('ai-models/tts/options/', CompanyTTSOptionsView.as_view(), name='company-tts-options'),
    path('ai-models/tts/default-voice/', CompanyTTSDefaultVoiceView.as_view(), name='company-tts-default-voice'),
    path('ai-models/tts/test/', CompanyTTSTestView.as_view(), name='company-tts-test'),
    path('ai-models/tts/runtime/', TTSRuntimeView.as_view(), name='tts-runtime'),
    path('ai-models/asr/status/', ASRStatusView.as_view(), name='asr-status'),
    path('ai-models/asr/config/', ASRConfigView.as_view(), name='asr-config'),
    path('ai-models/asr/device-status/', ASRDeviceStatusView.as_view(), name='asr-device-status'),
    path('ai-models/asr/test/', ASRTestView.as_view(), name='asr-test'),
] + router.urls
