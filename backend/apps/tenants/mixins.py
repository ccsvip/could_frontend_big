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

    def superuser_tenant_filter(self):
        """超管专用：解析 ?tenant=<id> 收窄维度。

        返回有效正整数 tenant_id；非法（非数字 / 空 / <=0）一律返回 None
        表示「不收窄」，退回 superuser 看全集的现状行为。

        注意：本方法只在 is_superuser 分支被调用，普通用户路径绝不读取
        ?tenant= 参数（防越权硬关卡）。
        """
        raw = self.request.query_params.get('tenant')
        if not raw:
            return None
        raw = raw.strip()
        if not raw.isdigit():
            return None
        value = int(raw)
        # 上界裁剪：tenant 主键为 bigint，超过上限的纯数字（isdigit 仍为 True）
        # 若直接 filter(tenant_id=...) 可能触发 Postgres integer out of range（500）。
        if value <= 0 or value > 9223372036854775807:
            return None
        return value

    def apply_tenant_scope(self, queryset):
        user = getattr(self.request, 'user', None)
        if user is not None and user.is_superuser:
            tenant_id = self.superuser_tenant_filter()
            if tenant_id is not None:
                return queryset.filter(tenant_id=tenant_id)
            return queryset
        # 非超管分支：仍按 membership 收敛，绝不读取 ?tenant= 参数。
        return queryset.for_tenant(self.request_tenant)

    def tenant_create_kwargs(self) -> dict:
        tenant = self.request_tenant
        # superuser 通过业务 API 写入不是受支持路径（D6：跨租户仅在 admin），不强行塞 tenant。
        return {'tenant': tenant} if tenant is not None else {}

    def get_queryset(self):
        return self.apply_tenant_scope(super().get_queryset())

    def perform_create(self, serializer):
        serializer.save(**self.tenant_create_kwargs())
