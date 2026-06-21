from rest_framework.routers import DefaultRouter

from .views import KnowledgeBaseViewSet, KnowledgeDocumentViewSet

router = DefaultRouter()
router.register('knowledge-bases', KnowledgeBaseViewSet, basename='knowledge-base-collection')
router.register('knowledge-base', KnowledgeDocumentViewSet, basename='knowledge-base')

urlpatterns = router.urls

