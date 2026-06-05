import logging

from apps.tenants.services import get_request_tenant

logger = logging.getLogger(__name__)

_ACTION_MAP = {
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}

_API_PREFIX = '/api/v1/'

_SKIP_PREFIXES = (
    '/api/v1/audit/',
    '/api/v1/auth/login/',
    '/api/v1/auth/refresh/',
)


class OperationLogMiddleware:
    """自动审计写操作的中间件。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:  # noqa: BLE001 - 审计绝不能影响主请求
            logger.exception('audit.operation_log.failed path=%s', getattr(request, 'path', '?'))
        return response

    def _maybe_log(self, request, response):
        method = request.method
        action = _ACTION_MAP.get(method)
        if action is None:
            return

        path = request.path
        if not path.startswith(_API_PREFIX):
            return
        if any(path.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return

        status_code = getattr(response, 'status_code', 500)
        if status_code >= 400:
            return

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            actor = user
            actor_username = user.get_username()
            actor_display_name = user.get_full_name() or actor_username
            from apps.accounts.services.permissions import get_role_payload

            role_payload = get_role_payload(user)
            actor_role_name = role_payload['name'] if role_payload else ''
        else:
            actor = None
            actor_username = ''
            actor_display_name = ''
            actor_role_name = ''

        tenant = self._resolve_tenant(request, user)

        # 延迟导入，避免应用加载顺序问题。
        from .descriptions import describe_operation
        from .models import OperationLog

        description = describe_operation(
            request=request,
            response=response,
            action=action,
            method=method,
            path=path,
        )

        OperationLog.objects.create(
            actor=actor,
            actor_username=actor_username,
            actor_display_name=actor_display_name,
            actor_role_name=actor_role_name,
            tenant=tenant,
            action=action,
            method=method,
            path=path[:512],
            description=description,
            status_code=status_code,
        )

    def _resolve_tenant(self, request, user):
        """普通用户取 membership 公司；超管操作始终记为平台日志。"""
        if user is not None and user.is_authenticated and user.is_superuser:
            return None
        return get_request_tenant(request)
