from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from apps.accounts.models import Menu, PermissionPoint, Role, UserRole

User = get_user_model()

ADMIN_ROLE_CODE = 'admin'
ADMIN_ROLE_NAME = '管理员'


def is_admin_user(user: User) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def get_bound_role(user: User) -> Role | None:
    if not user or not user.is_authenticated or is_admin_user(user):
        return None

    try:
        binding = user.role_binding
    except UserRole.DoesNotExist:
        return None

    role = binding.role
    if not role.is_active:
        return None

    return role


def get_role_payload(user: User) -> dict[str, str] | None:
    if not user or not user.is_authenticated:
        return None

    if is_admin_user(user):
        return {
            'code': ADMIN_ROLE_CODE,
            'name': ADMIN_ROLE_NAME,
        }

    role = get_bound_role(user)
    if role is None:
        return None

    return {
        'code': role.code,
        'name': role.name,
    }


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


def get_active_menus_for_user(user: User) -> list[dict[str, Any]]:
    if not user or not user.is_authenticated:
        return []

    if is_admin_user(user):
        menus = list(Menu.objects.filter(is_active=True).order_by('sort_order', 'id'))
    else:
        role = get_bound_role(user)
        if role is None:
            return []
        assigned_menus = list(role.menus.filter(is_active=True).order_by('sort_order', 'id'))
        menus = assigned_menus[:]
        seen_ids = {menu.id for menu in assigned_menus}

        for menu in assigned_menus:
            parent = menu.parent
            while parent and parent.is_active and parent.id not in seen_ids:
                menus.append(parent)
                seen_ids.add(parent.id)
                parent = parent.parent

    menu_map = {menu.id: menu for menu in menus}
    top_level_menus = [menu for menu in menus if menu.parent_id is None or menu.parent_id not in menu_map]
    top_level_menus.sort(key=lambda item: (item.sort_order, item.id))

    return [
        serialize_menu_tree(menu, menu_map)
        for menu in top_level_menus
    ]


def get_active_permission_codes_for_user(user: User) -> list[str]:
    if not user or not user.is_authenticated:
        return []

    if is_admin_user(user):
        permissions = PermissionPoint.objects.filter(is_active=True).order_by('module', 'code')
    else:
        role = get_bound_role(user)
        if role is None:
            return []
        permissions = role.permission_points.filter(is_active=True).order_by('module', 'code')

    return list(permissions.values_list('code', flat=True))


def build_user_access_context(user: User) -> dict[str, Any]:
    return {
        'role': get_role_payload(user),
        'menus': get_active_menus_for_user(user),
        'permissions': get_active_permission_codes_for_user(user),
    }
