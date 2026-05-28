from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AccountApplicationCreateView,
    AccountApplicationDetailView,
    AccountApplicationListView,
    ChangePasswordView,
    LoginView,
    MeView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('account-applications/', AccountApplicationCreateView.as_view(), name='account-application-create'),
    path('account-applications/manage/', AccountApplicationListView.as_view(), name='account-application-list'),
    path('account-applications/manage/<int:pk>/', AccountApplicationDetailView.as_view(), name='account-application-detail'),
]
