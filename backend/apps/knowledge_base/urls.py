from rest_framework.routers import DefaultRouter

from .views import KnowledgeDocumentViewSet

router = DefaultRouter()
router.register('knowledge-base', KnowledgeDocumentViewSet, basename='knowledge-base')

urlpatterns = router.urls

