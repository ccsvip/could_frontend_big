from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.tenants.services import get_user_tenant


class TenantAwareJWTAuthentication(JWTAuthentication):
    """拒绝公司被停用后仍持有旧 JWT 的普通成员。"""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        tenant = get_user_tenant(user)
        if tenant is not None and not tenant.is_active:
            raise AuthenticationFailed('公司已停用，请联系管理员', code='tenant_inactive')
        return user
