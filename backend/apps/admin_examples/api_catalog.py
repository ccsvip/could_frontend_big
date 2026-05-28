"""自动枚举 Django URL resolver 中的全部 /api/v1/* 接口。

供 admin_examples 后台「全部接口测试」页面动态生成接口下拉。

不使用 drf-spectacular 的 schema：直接走 Django URL resolver 本身，避免依赖
drf-spectacular 的 view inspector（一些自定义 APIView 不一定生成 schema）。
"""
from __future__ import annotations

import re
from typing import Any, Iterable, cast

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet, ViewSet


_API_PREFIX = '/api/v1/'

# DRF Router 默认 actions（standard）→ HTTP method。
_VIEWSET_DEFAULT_ACTIONS: dict[str, str] = {
    'list': 'GET',
    'retrieve': 'GET',
    'create': 'POST',
    'update': 'PUT',
    'partial_update': 'PATCH',
    'destroy': 'DELETE',
}


def _format_url_pattern(pattern: Any) -> str:
    """把 RoutePattern / RegexPattern 对象转成可读 URL 字符串。"""
    raw = str(pattern)
    # RoutePattern 形如 'commands/groups/<int:pk>/'，可直接用。
    # RegexPattern 形如 '^commands/groups/(?P<pk>[^/.]+)/$'，需要清理。
    if raw.startswith('^'):
        raw = raw[1:]
    if raw.endswith('$'):
        raw = raw[:-1]
    # 把命名捕获组 (?P<name>regex) 转成 <name>
    raw = re.sub(r'\(\?P<(?P<name>\w+)>[^)]+\)', r'<\g<name>>', raw)
    # 把匿名捕获组 (regex) 转成 <param>
    raw = re.sub(r'\([^)]*\)', '<param>', raw)
    return raw


def _walk(
    patterns: Iterable[Any],
    parent_prefix: str,
    out: list[dict[str, Any]],
) -> None:
    for p in patterns:
        if isinstance(p, URLResolver):
            sub_prefix = parent_prefix + _format_url_pattern(p.pattern)
            _walk(cast(Iterable[Any], cast(object, p.url_patterns)), sub_prefix, out)
            continue

        if not isinstance(p, URLPattern):
            continue

        full_path = '/' + (parent_prefix + _format_url_pattern(p.pattern)).lstrip('/')
        if not full_path.startswith(_API_PREFIX):
            continue
        # 跳过 schema/docs/redoc/api-root —— 测试这些没意义。
        if full_path in {'/api/v1/'} or full_path.startswith('/api/schema'):
            continue

        callback = p.callback
        view_class = getattr(callback, 'cls', None) or getattr(callback, 'view_class', None)
        view_name = view_class.__name__ if view_class is not None else callback.__name__
        actions: dict[str, str] | None = getattr(callback, 'actions', None)

        # ViewSet (router 注入了 actions={'get': 'list', ...})
        if actions:
            for http_method, action_name in actions.items():
                view_func = getattr(view_class, action_name, None) if view_class else None
                doc = (view_func.__doc__ or '').strip().splitlines()[0] if view_func and view_func.__doc__ else ''
                out.append({
                    'method': http_method.upper(),
                    'path': full_path,
                    'view': f'{view_name}.{action_name}',
                    'doc': doc or _viewset_default_doc(action_name, view_name),
                    'app': _app_label(view_class),
                })
            continue

        # 普通 APIView：检查它实现了哪些 HTTP method。
        if view_class is not None and _is_drf_view(view_class):
            for http_method in _http_methods_of(view_class):
                handler = getattr(view_class, http_method.lower(), None)
                doc = (handler.__doc__ or '').strip().splitlines()[0] if handler and handler.__doc__ else ''
                if not doc and view_class.__doc__:
                    doc = view_class.__doc__.strip().splitlines()[0]
                out.append({
                    'method': http_method.upper(),
                    'path': full_path,
                    'view': view_name,
                    'doc': doc,
                    'app': _app_label(view_class),
                })
            continue

        # 兜底：函数视图 / 非 DRF 视图，统一标记为 GET（测试时仍允许任意 method）。
        out.append({
            'method': 'GET',
            'path': full_path,
            'view': view_name,
            'doc': (callback.__doc__ or '').strip().splitlines()[0] if callback.__doc__ else '',
            'app': _module_app(callback.__module__) if hasattr(callback, '__module__') else '',
        })


def _viewset_default_doc(action: str, view_name: str) -> str:
    label = _VIEWSET_DEFAULT_ACTIONS.get(action)
    if action in _VIEWSET_DEFAULT_ACTIONS:
        return {
            'list': f'{view_name} 列表',
            'retrieve': f'{view_name} 详情',
            'create': f'{view_name} 创建',
            'update': f'{view_name} 整体更新',
            'partial_update': f'{view_name} 部分更新',
            'destroy': f'{view_name} 删除',
        }[action]
    return f'{view_name} - {action}'


def _is_drf_view(cls: type) -> bool:
    """是否 DRF APIView 系列（包括 ViewSet）。"""
    try:
        from rest_framework.views import APIView  # noqa: PLC0415
    except ImportError:
        return False
    return isinstance(cls, type) and issubclass(cls, APIView)


def _http_methods_of(cls: type) -> list[str]:
    """返回类实际声明的 HTTP method（按 DRF 约定）。"""
    methods = []
    for m in ('get', 'post', 'put', 'patch', 'delete'):
        if callable(getattr(cls, m, None)):
            methods.append(m.upper())
    if isinstance(cls, type) and issubclass(cls, (ViewSet, GenericViewSet, ModelViewSet, ReadOnlyModelViewSet)):
        # ViewSet 走 actions 分支，理论上不应该到这里。
        return methods or ['GET']
    return methods or ['GET']


def _app_label(view_class: type | None) -> str:
    if view_class is None:
        return ''
    return _module_app(view_class.__module__)


def _module_app(module: str) -> str:
    # apps.devices.views → devices；rest_framework_simplejwt.views → simplejwt
    if module.startswith('apps.'):
        return module.split('.')[1]
    if module.startswith('rest_framework_simplejwt'):
        return 'auth'
    return module.split('.')[0]


def list_api_endpoints() -> list[dict[str, Any]]:
    """返回去重排序后的全部 /api/v1/* 端点列表。

    每项形如：
        {
            'method': 'GET',
            'path': '/api/v1/devices/',
            'view': 'DeviceViewSet.list',
            'doc': 'DeviceViewSet 列表',
            'app': 'devices',
        }
    """
    resolver = get_resolver()
    out: list[dict[str, Any]] = []
    _walk(cast(Iterable[Any], cast(object, resolver.url_patterns)), '', out)

    # 去重：同 (method, path, view) 只保留一条。
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in out:
        key = (item['method'], item['path'], item['view'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda item: (item['app'], item['path'], item['method']))
    return deduped


def find_endpoint(method: str, path: str) -> dict[str, Any] | None:
    """根据 method+path 精确查找端点（用于校验用户输入）。"""
    method = method.upper()
    for item in list_api_endpoints():
        if item['method'] == method and item['path'] == path:
            return item
    return None


__all__ = ['list_api_endpoints', 'find_endpoint']
