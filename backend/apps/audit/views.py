from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanClearAuditLogs, CanViewAuditLogs
from apps.tenants.services import get_user_tenant

from .models import OperationLog
from .serializers import OperationLogSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['Audit'],
        parameters=[
            OpenApiParameter(
                name='tenant',
                type=int,
                location=OpenApiParameter.QUERY,
                description='按公司 ID 过滤操作日志',
            ),
        ],
    ),
    retrieve=extend_schema(tags=['Audit']),
)
class OperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """操作日志只读查询。

    通过 audit.logs.view 控制访问；公司管理员只能看本租户日志，超管可按 ?tenant= 过滤。
    """

    queryset = OperationLog.objects.select_related('actor', 'tenant').all()
    serializer_class = OperationLogSerializer
    permission_classes = [CanViewAuditLogs]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            raw_tenant = (self.request.query_params.get('tenant') or '').strip()
            if raw_tenant.isdigit():
                queryset = queryset.filter(tenant_id=int(raw_tenant))
            return queryset

        tenant = get_user_tenant(user)
        if tenant is None:
            return queryset.none()
        return queryset.filter(tenant=tenant)

    @action(detail=False, methods=['delete'], url_path='clear', permission_classes=[CanClearAuditLogs])
    def clear(self, request):
        user = request.user
        queryset = OperationLog.objects.all()
        if not user.is_superuser:
            tenant = get_user_tenant(user)
            if tenant is None:
                queryset = queryset.none()
            else:
                queryset = queryset.filter(tenant=tenant)

        deleted, _ = queryset.delete()
        return Response({'deleted': deleted})
