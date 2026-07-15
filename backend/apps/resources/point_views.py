from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny
from apps.accounts.authentication import TenantAwareJWTAuthentication
from apps.tenants.services import resolve_member_or_public_tenant, scope_queryset_member_or_public
from .point_models import Point
from .point_serializers import PointSerializer
from .views import PermissionMappedModelViewSet


_TRUTHY = {'1', 'true', 'yes'}


POINT_LIST_PARAMETERS = [
    OpenApiParameter(
        name='keyword',
        description='按点位名称 / 点位命令模糊搜索（icontains，大小写不敏感）。',
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name='is_active',
        description='按启用状态精确过滤：true 仅启用，false 仅停用，缺省不过滤。',
        required=False,
        type=bool,
    ),
    OpenApiParameter(
        name='include_hidden',
        description=(
            '是否在列表中包含被隐藏 / 停用的点位，仅对 list 动作生效。'
            '默认 false：列表只返回 is_active=true 且 is_show=true 的点位（供数字人运行时消费）；'
            '传 true / 1 / yes：返回全部点位（供后台管理界面切换开关）。'
            '注意：retrieve / update / destroy 等单条动作始终不受此参数影响，'
            '管理员可以正常对已隐藏 / 停用的点位发起读写。'
        ),
        required=False,
        type=bool,
    ),
    OpenApiParameter(
        name='all',
        description=(
            '是否一次性返回全部数据并跳过分页。'
            '传 true / 1 / yes：响应不再是 {count,next,previous,results} 分页结构，'
            '而是直接返回扁平的点位数组（适合数字人客户端一次拉满）。'
            '默认 false：保持分页（page / page_size）。'
        ),
        required=False,
        type=bool,
    ),
    OpenApiParameter(
        name='page',
        description='分页页码，从 1 开始；当 all=true 时被忽略。',
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name='page_size',
        description='分页大小，默认 10，最大 100；当 all=true 时被忽略。',
        required=False,
        type=int,
    ),
]


@extend_schema_view(
    list=extend_schema(
        tags=['Point Management'],
        summary='点位列表（支持过滤 / 隐藏 / 全量返回）',
        description=(
            '返回点位列表。默认情况下仅返回 is_active=true 且 is_show=true 的点位，'
            '适合数字人运行时消费；后台管理需要看到全部点位时请传 include_hidden=true。'
            '需要一次拉满（不分页）时传 all=true，响应将是扁平数组。'
        ),
        parameters=POINT_LIST_PARAMETERS,
    ),
    retrieve=extend_schema(tags=['Point Management']),
    create=extend_schema(tags=['Point Management']),
    update=extend_schema(tags=['Point Management']),
    partial_update=extend_schema(tags=['Point Management']),
    destroy=extend_schema(tags=['Point Management']),
)
class PointViewSet(PermissionMappedModelViewSet):
    # 仅启用 JWT 认证（不禁用）：带 token 的后台请求识别出 user 走 membership 隔离（防伪造），
    # 无 token 的数字人运行时请求仍放行，走 ?tenant=<code> 参数隔离。
    authentication_classes = [TenantAwareJWTAuthentication]
    permission_classes = [AllowAny]

    serializer_class = PointSerializer
    lookup_field = 'pk'
    permission_map = {
        # 'list': [],
        # 'retrieve': [],
        # 'create': [],
        # 'update': [],
        # 'partial_update': [],
        # 'destroy': [],
    }

    def get_permissions(self):
        """允许任何人访问，忽略父类基于 permission_map 的权限逻辑"""
        return [AllowAny()]

    def paginate_queryset(self, queryset):
        """支持 ?all=true 一次性返回全部数据（跳过分页）。"""
        all_flag = self.request.query_params.get('all', '').strip().lower()
        if all_flag in _TRUTHY:
            return None
        return super().paginate_queryset(queryset)

    def get_queryset(self):
        queryset = Point.objects.order_by('command', 'id')
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(command__icontains=keyword))

        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')

        # list 动作的运行时默认过滤：停用 or 隐藏 任一为真都不返回；
        # 后台管理页传 ?include_hidden=true 才能看到全部，便于切换两个开关。
        # retrieve / update / destroy 不过滤，否则隐藏点位将无法被 admin 操作回去。
        if getattr(self, 'action', None) == 'list':
            include_hidden = self.request.query_params.get('include_hidden', '').strip().lower()
            if include_hidden not in _TRUTHY:
                queryset = queryset.filter(is_active=True, is_show=True)
        # 登录后台用户走 membership 隔离；无登录态的数字人运行时走 ?tenant=<code>。
        return scope_queryset_member_or_public(queryset, self.request)

    def perform_create(self, serializer):
        tenant = resolve_member_or_public_tenant(self.request)
        if tenant is not None:
            serializer.save(tenant=tenant)
        else:
            serializer.save()
