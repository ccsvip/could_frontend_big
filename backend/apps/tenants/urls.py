from django.urls import path
from rest_framework.routers import DefaultRouter

from .employee_views import EmployeeViewSet, MyTenantCatalogView, TenantRoleViewSet
from .views import MenuCatalogView, TenantViewSet

router = DefaultRouter()
router.register('tenants', TenantViewSet, basename='tenant')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('roles', TenantRoleViewSet, basename='tenant-role')

urlpatterns = [
    path('menus/catalog/', MenuCatalogView.as_view(), name='menu-catalog'),
    path('my-tenant/catalog/', MyTenantCatalogView.as_view(), name='my-tenant-catalog'),
    *router.urls,
]
