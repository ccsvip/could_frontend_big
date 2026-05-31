from django.conf import settings
from django.db import models

from .managers import TenantManager


class Tenant(models.Model):
    """一家公司（租户）。所有业务数据按 tenant 行级隔离。"""

    name = models.CharField('公司名称', max_length=128)
    code = models.SlugField('公司标识', max_length=64, unique=True)
    is_active = models.BooleanField('是否启用', default=True)
    # 收容历史数据的「默认公司」标记为 legacy，后续 superuser 可在 admin 把行迁出。
    is_legacy = models.BooleanField('历史默认公司', default=False)
    # 超级管理员分配给本公司的菜单 / 权限点子集（公司可见范围的上界）。
    menus = models.ManyToManyField(
        'accounts.Menu',
        blank=True,
        related_name='tenants',
        verbose_name='可见菜单',
    )
    permission_points = models.ManyToManyField(
        'accounts.PermissionPoint',
        blank=True,
        related_name='tenants',
        verbose_name='可用权限点',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = '公司'
        verbose_name_plural = '公司'

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class Membership(models.Model):
    """user ↔ tenant 的归属关系。

    用独立一对一表挂租户，避免中途替换 AUTH_USER_MODEL 的高风险。
    superuser 不建 Membership —— 视为平台运维，跨租户能力仅在 Django admin。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership',
        verbose_name='用户',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name='所属公司',
    )
    # 公司管理员（申请审核通过的那个人）。员工为 False。
    is_tenant_admin = models.BooleanField('公司管理员', default=False)
    # 公司管理员建号 / 重置密码后置 True，员工首次登录强制改密。
    must_change_password = models.BooleanField('需强制改密', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['tenant_id', 'user_id']
        verbose_name = '公司成员'
        verbose_name_plural = '公司成员'

    def __str__(self) -> str:
        role = '管理员' if self.is_tenant_admin else '员工'
        return f'{self.user} @ {self.tenant.name} ({role})'
