from __future__ import annotations

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Menu, Role, UserRole
from apps.accounts.permissions import CanManageEmployees

from .employee_serializers import (
    EmployeeCreateSerializer,
    EmployeeSerializer,
    EmployeeUpdateSerializer,
    ResetPasswordSerializer,
    TenantRoleSerializer,
)
from .models import Membership
from .services import get_user_tenant
from .serializers import MenuCatalogItemSerializer, PermissionPointCatalogSerializer

User = get_user_model()


@extend_schema(tags=['Employees'])
class MyTenantCatalogView(APIView):
    """公司管理员视角的可分配目录：本公司被授权的业务菜单 + 权限点（供角色编辑器用）。"""

    permission_classes = [CanManageEmployees]

    def get(self, request):
        tenant = get_user_tenant(request.user)
        if tenant is None:
            return Response({'menus': [], 'permissionPoints': []})
        menus = tenant.menus.filter(is_active=True, audience=Menu.AUDIENCE_ALL).order_by('sort_order', 'id')
        perms = tenant.permission_points.filter(is_active=True).order_by('module', 'code')
        return Response({
            'menus': MenuCatalogItemSerializer(menus, many=True).data,
            'permissionPoints': PermissionPointCatalogSerializer(perms, many=True).data,
        })


@extend_schema_view(
    list=extend_schema(tags=['Employees']),
    retrieve=extend_schema(tags=['Employees']),
    create=extend_schema(tags=['Employees']),
    partial_update=extend_schema(tags=['Employees']),
)
class EmployeeViewSet(viewsets.ModelViewSet):
    """公司管理员管理本公司员工。作用域到本公司「非管理员」成员。"""

    permission_classes = [CanManageEmployees]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        tenant = get_user_tenant(self.request.user)
        if tenant is None:
            return User.objects.none()
        return (
            User.objects.filter(membership__tenant=tenant, membership__is_tenant_admin=False)
            .select_related('membership', 'role_binding__role')
            .order_by('-date_joined', 'id')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        if self.action == 'partial_update':
            return EmployeeUpdateSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(EmployeeSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(EmployeeSerializer(user).data)

    @extend_schema(tags=['Employees'], request=ResetPasswordSerializer)
    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data['newPassword'])
        user.save(update_fields=['password'])
        # 重置后强制员工下次登录改密。
        Membership.objects.filter(user=user).update(must_change_password=True)
        return Response({'status': 'success', 'message': '密码已重置，员工下次登录需修改密码'})


@extend_schema_view(
    list=extend_schema(tags=['Employees']),
    retrieve=extend_schema(tags=['Employees']),
    create=extend_schema(tags=['Employees']),
    update=extend_schema(tags=['Employees']),
    partial_update=extend_schema(tags=['Employees']),
    destroy=extend_schema(tags=['Employees']),
)
class TenantRoleViewSet(viewsets.ModelViewSet):
    """公司管理员管理本公司角色。菜单/权限点服务端钳制在公司被授权范围内。"""

    permission_classes = [CanManageEmployees]
    serializer_class = TenantRoleSerializer

    def get_queryset(self):
        tenant = get_user_tenant(self.request.user)
        if tenant is None:
            return Role.objects.none()
        return Role.objects.filter(tenant=tenant).prefetch_related('menus', 'permission_points').order_by('name', 'id')

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if UserRole.objects.filter(role=role).exists():
            return Response(
                {'status': 'error', 'message': '该角色仍有员工绑定，无法删除'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
