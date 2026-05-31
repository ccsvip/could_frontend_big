from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from .models import Membership, Tenant


def get_user_membership(user):
    """返回用户的 Membership；superuser / 未登录 / 无归属 均返回 None。"""
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    try:
        return user.membership
    except Membership.DoesNotExist:
        return None


def get_user_tenant(user) -> Tenant | None:
    """返回用户所属公司；superuser / 未登录 / 无归属 均返回 None。

    None 在业务作用域里表示「无租户上下文」：
    - superuser 走 admin 跨租户，前端业务查询对其返回 .all()（见 mixin）。
    - 普通用户若 None，则查询集收敛为空集。
    """
    membership = get_user_membership(user)
    return membership.tenant if membership is not None else None


def get_request_tenant(request) -> Tenant | None:
    """从请求解析租户，并在 request 上缓存，避免一次请求内重复查库。"""
    if request is None:
        return None
    if getattr(request, '_tenant_resolved', False):
        return request._tenant_cache
    tenant = get_user_tenant(getattr(request, 'user', None))
    request._tenant_resolved = True
    request._tenant_cache = tenant
    return tenant


def get_tenant_from_code_param(request) -> Tenant | None:
    """从公开端点的 ?tenant=<code> 查询参数解析租户（供无登录态的数字人运行时设备使用）。

    无参数 / 无效 code / 已停用公司 一律返回 None。
    """
    if request is None:
        return None
    code = (request.query_params.get('tenant') or '').strip()
    if not code:
        return None
    return Tenant.objects.filter(code=code, is_active=True).first()


def scope_queryset_member_or_public(queryset, request):
    """统一作用域：登录用户走 membership（管理端，防伪造），匿名走 ?tenant=<code>（运行时设备）。

    用于既服务后台管理、又服务数字人运行时的公开端点（Point / ScrollingText / 指令查询）。
    superuser 返回全集；无法解析租户时 for_tenant(None) 收敛为空集。
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        if user.is_superuser:
            return queryset
        return queryset.for_tenant(get_user_tenant(user))
    return queryset.for_tenant(get_tenant_from_code_param(request))


def resolve_member_or_public_tenant(request) -> Tenant | None:
    """解析单个租户用于写入：登录非超管→membership；匿名→?tenant=<code>；超管→None。"""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return None if user.is_superuser else get_user_tenant(user)
    return get_tenant_from_code_param(request)


def generate_unique_tenant_code(name: str) -> str:
    """从公司名生成唯一 slug code。中文名 slugify 后为空，回退到 'company' 并加序号去重。"""
    base = slugify(name) or 'company'
    base = base[:50]  # 给去重后缀留空间（SlugField max_length=64）
    code = base
    suffix = 2
    while Tenant.objects.filter(code=code).exists():
        code = f'{base}-{suffix}'
        suffix += 1
    return code


@transaction.atomic
def provision_company(*, name: str, admin_user) -> Tenant:
    """为审批通过的申请人开通公司：建 Tenant + 把申请人设为公司管理员。

    幂等：若该用户已有 Membership，直接返回其公司，不重复建租户
    （防止申请被多次保存/重复审批时产生重复公司）。
    """
    existing = get_user_membership(admin_user)
    if existing is not None:
        return existing.tenant

    tenant = Tenant.objects.create(name=name, code=generate_unique_tenant_code(name))
    Membership.objects.create(user=admin_user, tenant=tenant, is_tenant_admin=True)
    return tenant
