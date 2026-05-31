from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        """按租户过滤。tenant 为 None（无归属）时返回空集，杜绝裸查泄漏。"""
        if tenant is None:
            return self.none()
        return self.filter(tenant=tenant)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """tenant-scoped 模型的默认 manager。

    保留标准 .all()/.filter() 供 Django admin、Celery、数据迁移使用；
    业务请求路径一律通过 TenantScopedQuerysetMixin 走 .for_tenant()。
    """

    pass
