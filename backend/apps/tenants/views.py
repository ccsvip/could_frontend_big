from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountApplication, Menu, PermissionPoint
from apps.accounts.permissions import CanManageTenants

from .models import Tenant
from .serializers import (
    MenuCatalogItemSerializer,
    PermissionPointCatalogSerializer,
    TenantCreateSerializer,
    TenantMenuAssignmentSerializer,
    TenantSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Tenants']),
    retrieve=extend_schema(tags=['Tenants']),
    create=extend_schema(tags=['Tenants']),
    partial_update=extend_schema(tags=['Tenants']),
)
class TenantViewSet(viewsets.ModelViewSet):
    """平台超管管理所有公司。

    注意：这是平台级跨租户端点（superuser 专属，CanManageTenants 把关），
    故意 NOT 使用 TenantScopedQuerysetMixin —— 超管要看到全部公司。
    """

    queryset = Tenant.objects.all().order_by('-created_at', 'id')
    permission_classes = [CanManageTenants]
    # 不开放 DELETE（公司停用走 is_active / 双阶段删除，不硬删）；put 供 assign_menus action 使用。
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset
        include_hidden = self.request.query_params.get('include_hidden') == 'true'
        if include_hidden:
            return queryset
        approved_tenant_ids = AccountApplication.objects.filter(
            status=AccountApplication.STATUS_APPROVED,
            tenant__isnull=False,
        ).values_list('tenant_id', flat=True)
        return queryset.filter(id__in=approved_tenant_ids, is_active=True, is_legacy=False)

    def get_serializer_class(self):
        if self.action == 'create':
            return TenantCreateSerializer
        if self.action == 'assign_menus':
            return TenantMenuAssignmentSerializer
        return TenantSerializer

    @extend_schema(tags=['Tenants'], request=TenantMenuAssignmentSerializer, responses=TenantSerializer)
    @action(detail=True, methods=['get', 'put'], url_path='menus')
    def assign_menus(self, request, pk=None):
        tenant = self.get_object()
        if request.method == 'GET':
            # 返回该公司当前被分配的菜单 id 与权限点 id，供分配器回显。
            return Response({
                'menuIds': list(tenant.menus.values_list('id', flat=True)),
                'permissionPointIds': list(tenant.permission_points.values_list('id', flat=True)),
            })

        serializer = TenantMenuAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=tenant)
        return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)


@extend_schema(tags=['Tenants'])
class MenuCatalogView(APIView):
    """给超管分配器用的全局目录：可分配业务菜单（audience=all） + 权限点。"""

    permission_classes = [CanManageTenants]

    def get(self, request):
        menus = Menu.objects.filter(is_active=True, audience=Menu.AUDIENCE_ALL).order_by('sort_order', 'id')
        permission_points = PermissionPoint.objects.filter(is_active=True).order_by('module', 'code')
        return Response({
            'menus': MenuCatalogItemSerializer(menus, many=True).data,
            'permissionPoints': PermissionPointCatalogSerializer(permission_points, many=True).data,
        })
