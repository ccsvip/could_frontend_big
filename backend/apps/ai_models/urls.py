from rest_framework.routers import DefaultRouter

from .views import ChatConversationViewSet, LLMProviderViewSet

router = DefaultRouter()
router.register('ai-models/llm-providers', LLMProviderViewSet, basename='llm-provider')
router.register('ai-models/chat/conversations', ChatConversationViewSet, basename='chat-conversation')

urlpatterns = router.urls
