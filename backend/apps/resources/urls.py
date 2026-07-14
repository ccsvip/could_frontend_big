from django.urls import path
from rest_framework.routers import DefaultRouter

from .point_views import PointViewSet
from .views import (
    CommandDataLookupView,
    CommandExportCommandsView,
    CommandExportEnabledGroupsView,
    CommandGroupViewSet,
    ControlCommandRecognitionPolicyView,
    ControlCommandViewSet,
    ImageResourceViewSet,
    MinioSettingsView,
    MinioTenantQuotaView,
    ModelAssetViewSet,
    ResourceUploadConfigView,
    ResourceUploadPresignView,
    ScrollingTextViewSet,
    TaskCommandViewSet,
    VideoUploadConfigView,
    VideoUploadPresignView,
    VideoResourceViewSet,
    VoiceToneViewSet,
)

router = DefaultRouter()
router.register('resources/images', ImageResourceViewSet, basename='resource-image')
router.register('resources/videos', VideoResourceViewSet, basename='resource-video')
router.register('resources/scrolling-texts', ScrollingTextViewSet, basename='scrolling-text')
router.register('resources/voice-tones', VoiceToneViewSet, basename='voice-tone')
router.register('resources/models', ModelAssetViewSet, basename='model-asset')
router.register('commands/groups', CommandGroupViewSet, basename='command-group')
router.register('commands/control', ControlCommandViewSet, basename='control-command')
router.register('commands/tasks', TaskCommandViewSet, basename='task-command')
router.register('commands/points', PointViewSet, basename='point')

urlpatterns = [
    path('settings/minio/', MinioSettingsView.as_view(), name='minio-settings'),
    path('settings/minio/quotas/', MinioTenantQuotaView.as_view(), name='minio-tenant-quotas'),
    path('resources/upload-config/', ResourceUploadConfigView.as_view(), name='resource-upload-config'),
    path('resources/presign/', ResourceUploadPresignView.as_view(), name='resource-upload-presign'),
    path('resources/videos/upload-config/', VideoUploadConfigView.as_view(), name='video-upload-config'),
    path('resources/videos/presign/', VideoUploadPresignView.as_view(), name='video-upload-presign'),
    path('commands/data/', CommandDataLookupView.as_view(), name='command-data-lookup'),
    path('commands/control-recognition-policy/', ControlCommandRecognitionPolicyView.as_view(), name='control-command-recognition-policy'),
    path('commands/export/enabled-groups/', CommandExportEnabledGroupsView.as_view(), name='command-export-enabled-groups'),
    path('commands/export/commands/', CommandExportCommandsView.as_view(), name='command-export-commands'),
    *router.urls,
]
