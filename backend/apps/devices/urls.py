from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    DeviceActivationView,
    DeviceApplicationViewSet,
    DeviceAuthorizationCodeViewSet,
    DeviceAuthorizationRequestViewSet,
    DeviceGroupViewSet,
    DeviceRuntimeConfigView,
    DeviceRuntimeHeartbeatView,
    DeviceViewSet,
)

router = DefaultRouter()
router.register('devices', DeviceViewSet, basename='device')
router.register('device-groups', DeviceGroupViewSet, basename='device-group')
router.register('device-applications', DeviceApplicationViewSet, basename='device-application')
router.register('device-authorization-codes', DeviceAuthorizationCodeViewSet, basename='device-authorization-code')
router.register('device-authorization-requests', DeviceAuthorizationRequestViewSet, basename='device-authorization-request')

urlpatterns = [
    path('device-auth/activate/', DeviceActivationView.as_view(), name='device-auth-activate'),
    path('device-runtime/config/', DeviceRuntimeConfigView.as_view(), name='device-runtime-config'),
    path('device-runtime/heartbeat/', DeviceRuntimeHeartbeatView.as_view(), name='device-runtime-heartbeat'),
    *router.urls,
]
