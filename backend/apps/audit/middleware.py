import logging

from apps.tenants.services import get_request_tenant

logger = logging.getLogger(__name__)

# 写操作 HTTP 方法 → 审计动作映射。
_ACTION_MAP = {
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}

# 只审计 REST 业务前缀下的写操作。
_API_PREFIX = '/api/v1/'

# 不审计的路径前缀：
# - audit 自身：避免「查看日志页面触发写操作」式的自我记录死循环（其实 audit 只读，但仍显式排除）。
# - 登录/刷新 token：这些请求体里有明文密码 / refresh token，连「发生过一次登录」这种元数据也不入审计表，
#   降低日志被用于账号枚举的风险，且登录尚未鉴权，actor 解析也无意义。
_SKIP_PREFIXES = (
    '/api/v1/audit/',
    '/api/v1/auth/login/',
    '/api/v1/auth/refresh/',
)


class OperationLogMiddleware:
    """自动审计写操作的中间件。

    记录规则（全部满足才记一条）：
    1. path 以 /api/v1/ 开头；
    2. method ∈ {POST, PUT, PATCH, DELETE}；
    3. 不在 _SKIP_PREFIXES 跳过名单内；
    4. 响应 status_code < 400（即写操作成功，4xx/5xx 失败不留痕）。

    只记录元数据（操作人、公司、动作、method、path、状态码、时间），
    绝不存储 request/response body —— 防止把密码、token、API Key、密钥等敏感正文写进日志表。

    必须放在 AuthenticationMiddleware 之后，保证响应阶段 request.user 已就绪
    （DRF 的 JWT 鉴权会把认证用户回写到底层 Django request.user，故响应阶段可读到）。
    写日志失败一律 try/except 吞掉，绝不阻断或污染主请求响应。
    """

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
        else:
            actor = None
            actor_username = ''

        tenant = self._resolve_tenant(request, user)

        # 延迟导入，避免应用加载顺序问题。
        from .models import OperationLog

        OperationLog.objects.create(
            actor=actor,
            actor_username=actor_username,
            tenant=tenant,
            action=action,
            method=method,
            path=path[:512],
            status_code=status_code,
        )

    def _resolve_tenant(self, request, user):
        """普通用户取其 membership 公司；超管带 ?tenant=<id> 时取该公司，否则 None。"""
        tenant = get_request_tenant(request)
        if tenant is not None:
            return tenant
        if user is not None and user.is_authenticated and user.is_superuser:
            raw = (request.GET.get('tenant') or '').strip()
            if raw.isdigit():
                from apps.tenants.models import Tenant
                return Tenant.objects.filter(pk=int(raw)).first()
        return None
