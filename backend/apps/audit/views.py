from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.accounts.permissions import IsSuperUser

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

    平台超管专属（IsSuperUser 把关，仅 is_superuser 放行）。
    注意：不可改用 CanManageTenants —— tenant.management.view 对 is_staff 也发放，
    会让非超管 staff 横向读到全平台日志。
    支持 ?tenant=<id> 按公司过滤；默认分页（StandardPageNumberPagination）。
    日志为系统自动写入，不提供任何写接口。
    """

    queryset = OperationLog.objects.select_related('actor', 'tenant').all()
    serializer_class = OperationLogSerializer
    permission_classes = [IsSuperUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        raw_tenant = (self.request.query_params.get('tenant') or '').strip()
        if raw_tenant.isdigit():
            queryset = queryset.filter(tenant_id=int(raw_tenant))
        return queryset
