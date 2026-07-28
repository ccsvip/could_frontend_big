from django.urls import path

from .views import ErrorCodeDetailView, ErrorCodeListView


urlpatterns = [
    path('error-codes/', ErrorCodeListView.as_view(), name='error-code-list'),
    path('error-codes/<str:code>/', ErrorCodeDetailView.as_view(), name='error-code-detail'),
]
