from __future__ import annotations

import os
from typing import Any

from celery import current_app
from django.contrib import admin, messages
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django_celery_beat.models import PeriodicTask
from django_celery_results.models import TaskResult

from apps.devices.tasks import refresh_device_stats
from config.tasks import cleanup_old_celery_results


def operations_dashboard_view(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('仅超级管理员可访问系统运维面板')

    if request.method == 'POST':
        handle_operations_post(request)
        return redirect(reverse('admin-operations-dashboard'))

    context = {
        **admin.site.each_context(request),
        **get_operations_context(),
    }
    return TemplateResponse(request, 'admin/operations_dashboard.html', context)


def handle_operations_post(request):
    action = request.POST.get('action', '').strip()
    try:
        # 只允许明确白名单内的安全运维任务，避免后台页面演变成高风险控制台。
        if action == 'refresh_device_stats':
            refresh_device_stats.delay()
            messages.success(request, '已投递设备统计刷新任务')
            return

        if action == 'cleanup_old_celery_results':
            cleanup_old_celery_results.delay()
            messages.success(request, '已投递旧任务结果清理任务')
            return
    except Exception as exc:
        messages.error(request, f'运维任务投递失败：{exc}')
        return

    messages.error(request, '未知运维操作，未执行')


def get_operations_context() -> dict[str, Any]:
    db_status = get_database_status()
    cache_status = get_cache_status()
    worker_status = get_celery_worker_status()
    beat_status = get_celery_beat_configuration_status()
    statuses = [db_status, cache_status, worker_status, beat_status]
    all_ok = all(status['ok'] for status in statuses)

    return {
        'title': '系统运维',
        'summary': {
            'ok': all_ok,
            'label': '正常' if all_ok else '异常',
            'message': '运维状态正常' if all_ok else '存在需要处理的运维状态',
        },
        'statuses': statuses,
        'worker_status': worker_status,
        'beat_status': beat_status,
        'recent_results': get_recent_task_results(),
        'flower_url': os.getenv('FLOWER_URL', '').strip(),
    }


def get_database_status() -> dict[str, Any]:
    try:
        connection.ensure_connection()
    except Exception as exc:
        return make_status('数据库', False, f'数据库连接异常：{exc}')
    return make_status('数据库', True, '数据库连接正常')


def get_cache_status() -> dict[str, Any]:
    try:
        cache.set('operations-admin:ping', 'ok', timeout=5)
        is_connected = cache.get('operations-admin:ping') == 'ok'
    except Exception as exc:
        return make_status('Redis 缓存', False, f'Redis 缓存异常：{exc}')
    return make_status('Redis 缓存', is_connected, 'Redis 缓存连接正常' if is_connected else 'Redis 缓存连接异常')


def get_celery_worker_status() -> dict[str, Any]:
    try:
        inspector = current_app.control.inspect(timeout=1)
        ping_response = inspector.ping() or {}
        registered_response = inspector.registered() or {}
    except Exception as exc:
        return {
            **make_status('Celery worker', False, f'Celery worker 检查异常：{exc}'),
            'registered_tasks': [],
            'nodes': [],
        }

    registered_tasks = sorted({task for tasks in registered_response.values() for task in tasks})
    nodes = sorted(set(ping_response.keys()) | set(registered_response.keys()))
    is_online = bool(nodes)
    return {
        **make_status('Celery worker', is_online, 'Celery worker 在线' if is_online else '未检测到 Celery worker'),
        'registered_tasks': registered_tasks,
        'nodes': nodes,
    }


def get_celery_beat_configuration_status() -> dict[str, Any]:
    try:
        # 第一版只检查数据库调度器配置，不把它包装成 beat 进程存活状态。
        cleanup_task_exists = PeriodicTask.objects.filter(name='清理 7 天前 Celery 任务结果').exists()
        total_tasks = PeriodicTask.objects.count()
    except Exception as exc:
        return make_status('Celery beat 调度器配置', False, f'周期任务表异常：{exc}')

    if cleanup_task_exists:
        return make_status('Celery beat 调度器配置', True, f'周期任务表可用，已配置清理任务，共 {total_tasks} 个周期任务')
    return make_status('Celery beat 调度器配置', False, '周期任务表可用，但未找到任务结果清理任务')


def get_recent_task_results(limit: int = 50) -> list[dict[str, Any]]:
    results = TaskResult.objects.order_by('-date_done', '-date_created')[:limit]
    return [format_task_result(result) for result in results]


def format_task_result(result: TaskResult) -> dict[str, Any]:
    # task_name 可能为空，按固定降级顺序展示，避免排障时出现空白任务名。
    task_label = (result.task_name or '').strip() or result.task_id or '未知任务'
    summary_source = result.traceback or result.result or ''
    return {
        'task_name': task_label,
        'task_id': result.task_id,
        'status': result.status,
        'date_done': result.date_done,
        'summary': str(summary_source)[:240],
    }


def make_status(name: str, ok: bool, message: str) -> dict[str, Any]:
    return {
        'name': name,
        'ok': ok,
        'label': '正常' if ok else '异常',
        'message': message,
    }
