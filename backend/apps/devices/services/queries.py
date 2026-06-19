from __future__ import annotations

from collections.abc import Mapping

from django.db.models import Prefetch, Q, QuerySet

from apps.devices.models import Device, DeviceAuthLog


AUTHORIZATION_LOG_ACTIONS = {
    DeviceAuthLog.ACTION_ACTIVATE,
    DeviceAuthLog.ACTION_BIND,
    DeviceAuthLog.ACTION_IGNORE,
    DeviceAuthLog.ACTION_AUTHORIZE,
    DeviceAuthLog.ACTION_REVOKE,
}


def _param(params: Mapping | None, name: str) -> str:
    if params is None:
        return ''
    if hasattr(params, 'get'):
        value = params.get(name, '')
    else:
        value = ''
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ''
    return str(value or '').strip()


def device_authorization_requests_queryset(params: Mapping | None = None) -> QuerySet[Device]:
    activation_logs = DeviceAuthLog.objects.filter(
        action=DeviceAuthLog.ACTION_ACTIVATE,
    ).order_by('-created_at', '-id')
    queryset = (
        Device.objects.select_related('tenant', 'application', 'agent_application', 'group')
        .filter(auth_logs__action=DeviceAuthLog.ACTION_ACTIVATE)
        .prefetch_related(Prefetch('auth_logs', queryset=activation_logs, to_attr='activation_logs_for_request'))
        .distinct()
        .order_by('-updated_at', '-id')
    )
    binding_status = _param(params, 'bindingStatus')
    if binding_status == 'pending':
        queryset = queryset.filter(tenant__isnull=True, authorization_ignored_at__isnull=True)
    if binding_status == 'bound':
        queryset = queryset.filter(tenant__isnull=False)
    if binding_status == 'ignored':
        queryset = queryset.filter(tenant__isnull=True, authorization_ignored_at__isnull=False)
    keyword = _param(params, 'keyword')
    if keyword:
        queryset = queryset.filter(Q(code__icontains=keyword) | Q(name__icontains=keyword))
    tenant_id = _param(params, 'tenantId')
    if tenant_id.isdigit():
        queryset = queryset.filter(tenant_id=int(tenant_id))
    return queryset


def device_authorization_logs_queryset(params: Mapping | None = None) -> QuerySet[DeviceAuthLog]:
    queryset = DeviceAuthLog.objects.select_related('tenant', 'application', 'agent_application', 'device__agent_application').filter(
        action__in=AUTHORIZATION_LOG_ACTIONS,
    ).order_by('-created_at', '-id')
    tenant_id = _param(params, 'tenantId')
    if tenant_id.isdigit():
        queryset = queryset.filter(tenant_id=int(tenant_id))
    keyword = _param(params, 'keyword')
    if keyword:
        queryset = queryset.filter(Q(code__icontains=keyword) | Q(device__name__icontains=keyword))
    return queryset


def device_authorizations_queryset(params: Mapping | None = None) -> QuerySet[Device]:
    queryset = (
        Device.objects.select_related('tenant', 'application', 'agent_application', 'group')
        .filter(tenant__isnull=False)
        .order_by('-updated_at', '-id')
    )
    tenant_id = _param(params, 'tenantId')
    if tenant_id.isdigit():
        queryset = queryset.filter(tenant_id=int(tenant_id))
    keyword = _param(params, 'keyword')
    if keyword:
        queryset = queryset.filter(Q(code__icontains=keyword) | Q(name__icontains=keyword))
    return queryset
