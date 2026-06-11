"""测试辅助：给「单租户时代」的旧测试补上租户上下文。

PR-2 给业务表加了行级隔离后，旧测试的用户没有 Membership（→ for_tenant(None) → 空集 → 404），
且 ORM 直建的业务对象 tenant=None（不属于任何公司）。本 mixin 提供最小补丁：
- setup_tenant(user)：建一个测试公司并给用户挂 Membership，使其请求解析到该租户。
- 业务对象创建时显式传 tenant=self.tenant 归属到同一公司。

注意：本 mixin 只补「租户上下文」，不改变任何被测行为或断言。
"""
from apps.accounts.models import Menu, PermissionPoint
from apps.tenants.models import Membership, Tenant


class TenantTestMixin:
    tenant_code = 'test-tenant'
    tenant_name = '测试公司'

    def setup_tenant(self, user, *, is_tenant_admin=False):
        self.tenant = Tenant.objects.create(name=self.tenant_name, code=self.tenant_code)
        Membership.objects.create(user=user, tenant=self.tenant, is_tenant_admin=is_tenant_admin)
        self.grant_all_scope_to_tenant()
        return self.tenant

    def grant_all_scope_to_tenant(self):
        """给测试公司授予「全量」菜单 + 权限点（镜像「默认公司」迁移）。

        普通员工权限直接来自 tenant.permission_points；旧单租户测试的公司若没被授权
        任何权限点，会全部 403。真实运营公司由超管授权过，故测试公司也应被授权全量。
        tests 里惰性新建权限点后需再次同步到 tenant.permission_points。
        """
        self.tenant.menus.set(Menu.objects.all())
        self.tenant.permission_points.set(PermissionPoint.objects.all())
