from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    ASRDeviceStatusView,
    ASRSettingsTestView,
    ASRSettingsView,
    ASRStatusView,
    ASRTestView,
    ASRReplacementRuleViewSet,
    ChatConversationViewSet,
    LLMProviderViewSet,
)

router = DefaultRouter()
router.register('ai-models/llm-providers', LLMProviderViewSet, basename='llm-provider')
router.register('ai-models/asr/replacement-rules', ASRReplacementRuleViewSet, basename='asr-replacement-rule')
router.register('ai-models/chat/conversations', ChatConversationViewSet, basename='chat-conversation')

urlpatterns = [
    path('settings/asr/', ASRSettingsView.as_view(), name='asr-settings'),
    path('settings/asr/test/', ASRSettingsTestView.as_view(), name='asr-settings-test'),
    path('ai-models/asr/status/', ASRStatusView.as_view(), name='asr-status'),
    path('ai-models/asr/device-status/', ASRDeviceStatusView.as_view(), name='asr-device-status'),
    path('ai-models/asr/test/', ASRTestView.as_view(), name='asr-test'),
] + router.urls
