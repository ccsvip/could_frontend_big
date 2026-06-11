from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from apps.accounts.models import Menu, PermissionPoint

User = get_user_model()

ADMIN_ROLE_CODE = 'admin'
ADMIN_ROLE_NAME = '管理员'

# 平台/公司管理员专属权限码（PR-4 迁移中 seed 对应 PermissionPoint）。
TENANT_MANAGEMENT_VIEW_CODE = 'tenant.management.view'
TENANT_EMPLOYEES_MANAGE_CODE = 'tenant.employees.manage'
AUDIT_LOGS_VIEW_CODE = 'audit.logs.view'


def is_admin_user(user: User) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def get_role_payload(user: User) -> dict[str, str] | None:
    if not user or not user.is_authenticated:
        return None

    if is_admin_user(user):
        return {
            'code': ADMIN_ROLE_CODE,
            'name': ADMIN_ROLE_NAME,
        }

    membership = _get_membership(user)
    if membership is not None and membership.is_tenant_admin:
        return {
            'code': 'tenant_admin',
            'name': '公司管理员',
        }
    if membership is not None:
        return {
            'code': 'employee',
            'name': membership.role_name or '公司员工',
        }

    return None


def _get_membership(user: User):
    """懒加载 membership，避免 accounts ↔ tenants 的 app 加载/循环导入问题。"""
    from apps.tenants.services import get_user_membership
    return get_user_membership(user)


def _collect_with_ancestors(assigned_menus: list[Menu]) -> list[Menu]:
    """把一组菜单连同其全部启用的祖先收集成扁平列表（保证菜单树可渲染）。"""
    menus = list(assigned_menus)
    seen_ids = {menu.id for menu in menus}
    for menu in assigned_menus:
        parent = menu.parent
        while parent and parent.is_active and parent.id not in seen_ids:
            menus.append(parent)
            seen_ids.add(parent.id)
            parent = parent.parent
    return menus


def serialize_menu_tree(menu: Menu, menu_map: dict[int, Menu]) -> dict[str, Any]:
    children = [
        child
        for child in menu_map.values()
        if child.parent_id == menu.id and child.is_active
    ]
    children.sort(key=lambda item: (item.sort_order, item.id))

    payload = {
        'key': menu.path,
        'label': menu.name,
        'path': menu.path,
        'icon': menu.icon,
    }
    if children:
        payload['children'] = [serialize_menu_tree(child, menu_map) for child in children]
    return payload


def _assemble_menu_tree(menus: list[Menu]) -> list[dict[str, Any]]:
    """把一组菜单（已含祖先）组装成前端可渲染的菜单树。"""
    menu_map = {menu.id: menu for menu in menus}
    top_level_menus = [menu for menu in menus if menu.parent_id is None or menu.parent_id not in menu_map]
    top_level_menus.sort(key=lambda item: (item.sort_order, item.id))
    return [serialize_menu_tree(menu, menu_map) for menu in top_level_menus]


def get_active_menus_for_user(user: User) -> list[dict[str, Any]]:
    if not user or not user.is_authenticated:
        return []

    # 超管（平台运维）：通用业务菜单 + 平台专属（租户管理）；不含「员工管理」这类公司管理员专属。
    if is_admin_user(user):
        menus = list(
            Menu.objects.filter(is_active=True)
            .exclude(audience=Menu.AUDIENCE_TENANT_ADMIN)
            .order_by('sort_order', 'id')
        )
        return _assemble_menu_tree(menus)

    membership = _get_membership(user)
    if membership is None:
        return []
    tenant = membership.tenant
    if not tenant.is_active:
        return []

    if membership.is_tenant_admin:
        # 公司管理员：超管分配给本公司的菜单（均为通用业务菜单） + 所有「公司管理员专属」菜单（员工管理）。
        assigned = list(
            tenant.menus.filter(is_active=True, audience=Menu.AUDIENCE_ALL).order_by('sort_order', 'id')
        )
        admin_only = list(
            Menu.objects.filter(is_active=True, audience=Menu.AUDIENCE_TENANT_ADMIN).order_by('sort_order', 'id')
        )
        menus = _collect_with_ancestors(assigned + admin_only)
        return _assemble_menu_tree(menus)

    # 员工：本公司被分配的业务菜单。公司管理员仅额外多员工管理菜单。
    assigned = list(
        tenant.menus.filter(is_active=True, audience=Menu.AUDIENCE_ALL).order_by('sort_order', 'id')
    )
    menus = _collect_with_ancestors(assigned)
    return _assemble_menu_tree(menus)


def get_active_permission_codes_for_user(user: User) -> list[str]:
    if not user or not user.is_authenticated:
        return []

    # 超管：全部权限点。
    if is_admin_user(user):
        codes = PermissionPoint.objects.filter(is_active=True).order_by('module', 'code').values_list('code', flat=True)
        return list(codes)

    membership = _get_membership(user)
    if membership is None:
        return []
    tenant = membership.tenant
    if not tenant.is_active:
        return []

    if membership.is_tenant_admin:
        # 公司管理员：本公司被授权的权限点 + 员工管理能力（额外的、不依赖授权的固有能力）。
        codes = set(
            tenant.permission_points.filter(is_active=True).values_list('code', flat=True)
        )
        codes.add(TENANT_EMPLOYEES_MANAGE_CODE)
        codes.add(AUDIT_LOGS_VIEW_CODE)
        return sorted(codes)

    # 员工：默认拥有本公司被授权的业务权限点，但不能获得员工管理能力。
    codes = set(
        tenant.permission_points.filter(is_active=True)
        .exclude(code=TENANT_EMPLOYEES_MANAGE_CODE)
        .values_list('code', flat=True)
    )
    return sorted(codes)


def build_user_access_context(user: User) -> dict[str, Any]:
    return {
        'role': get_role_payload(user),
        'menus': get_active_menus_for_user(user),
        'permissions': get_active_permission_codes_for_user(user),
    }
