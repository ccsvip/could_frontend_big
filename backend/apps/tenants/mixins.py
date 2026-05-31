from apps.tenants.services import get_request_tenant


class TenantScopedQuerysetMixin:
    """给 DRF ViewSet 注入租户作用域（三道防线之第二道）。

    用法：
    - 无自定义 get_queryset 的视图：把本 mixin 放在 Cached 之后、PermissionMapped 之前，
      get_queryset 自动按租户收窄。
    - 已自定义 get_queryset 的视图（resources / knowledge_base）：在其 get_queryset
      末尾改为 `return self.apply_tenant_scope(queryset)`。
    - 已自定义 perform_create 的视图：把 `serializer.save()` 改为
      `serializer.save(**self.tenant_create_kwargs())`。

    MRO 约定：本 mixin 的 perform_create 是「终结写入」（不再 super），因此当与
    CachedBusinessResponseMixin 同用时，必须把 Cached 放在本 mixin 之前，
    让 Cached.perform_create 先 wrap、再 super 到本 mixin 完成带 tenant 的写入并清缓存。

    superuser 视为平台运维（无 Membership），业务查询对其返回全集；普通用户无归属时
    for_tenant(None) 收敛为空集，杜绝裸查泄漏。
    """

    @property
    def request_tenant(self):
        return get_request_tenant(self.request)

    def apply_tenant_scope(self, queryset):
        user = getattr(self.request, 'user', None)
        if user is not None and user.is_superuser:
            return queryset
        return queryset.for_tenant(self.request_tenant)

    def tenant_create_kwargs(self) -> dict:
        tenant = self.request_tenant
        # superuser 通过业务 API 写入不是受支持路径（D6：跨租户仅在 admin），不强行塞 tenant。
        return {'tenant': tenant} if tenant is not None else {}

    def get_queryset(self):
        return self.apply_tenant_scope(super().get_queryset())

    def perform_create(self, serializer):
        serializer.save(**self.tenant_create_kwargs())
