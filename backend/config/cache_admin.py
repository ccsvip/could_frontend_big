from __future__ import annotations

from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .business_cache import (
    BUSINESS_CACHE_NAMESPACE_MAP,
    clear_all_business_cache,
    clear_business_cache_namespace,
    get_business_cache_summaries,
)


def cache_management_view(request):
    if request.method == 'POST':
        handle_cache_management_post(request)
        return redirect(reverse('admin-cache-management'))

    context = {
        **admin.site.each_context(request),
        'title': 'Redis 缓存管理',
        'cache_status': get_cache_status(),
        'summaries': get_business_cache_summaries(),
    }
    return TemplateResponse(request, 'admin/cache_management.html', context)


def handle_cache_management_post(request):
    action = request.POST.get('action', '').strip()
    if action == 'clear_all':
        deleted_count = clear_all_business_cache()
        messages.success(request, f'已清理全部业务缓存，共 {deleted_count} 个缓存键')
        return

    if action == 'clear_namespace':
        namespace = request.POST.get('namespace', '').strip()
        namespace_config = BUSINESS_CACHE_NAMESPACE_MAP.get(namespace)
        if namespace_config is None:
            messages.error(request, '缓存模块不存在，未执行清理')
            return

        deleted_count = clear_business_cache_namespace(namespace)
        messages.success(request, f'已清理 {namespace_config.label} 缓存，共 {deleted_count} 个缓存键')
        return

    messages.error(request, '未知缓存操作，未执行清理')


def get_cache_status() -> dict[str, str | bool]:
    try:
        cache.set('business-cache:admin:ping', 'ok', timeout=5)
        is_connected = cache.get('business-cache:admin:ping') == 'ok'
    except Exception as exc:
        return {
            'isConnected': False,
            'message': str(exc),
        }

    return {
        'isConnected': is_connected,
        'message': 'Redis 缓存连接正常' if is_connected else 'Redis 缓存连接异常',
    }
