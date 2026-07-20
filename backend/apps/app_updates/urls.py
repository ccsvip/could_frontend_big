from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppReleaseDownloadView, AppReleaseViewSet, AppUpdateCheckView, AppUpdateReportView

router = DefaultRouter()
router.register('app-update-releases', AppReleaseViewSet, basename='app-update-release')

urlpatterns = [
    path('app-updates/check/', AppUpdateCheckView.as_view(), name='app-update-check'),
    path('app-updates/report/', AppUpdateReportView.as_view(), name='app-update-report'),
    path('app-update-releases/<str:release_id>/apk/', AppReleaseDownloadView.as_view(), name='app-update-release-download'),
    *router.urls,
]

