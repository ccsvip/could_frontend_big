from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as AuthUser
from django.db import models

User = get_user_model()


class AccountUser(AuthUser):
    """auth.User 的 proxy，用于把"用户"管理挂到 accounts app 的「账号管理」分组下。

    数据库不变，仍读写 auth_user 表；只是 admin 注册路径从 /admin/auth/user/
    迁到 /admin/accounts/user/，与 AccountApplication / Role / Menu 等同组显示。
    """

    class Meta:
        proxy = True
        app_label = 'accounts'
        verbose_name = '用户'
        verbose_name_plural = '用户'


class AccountApplication(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待审核'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已拒绝'),
    ]

    username = models.CharField('登录用户名', max_length=150, unique=True, null=True, blank=True)
    applicant_name = models.CharField('申请人姓名', max_length=64)
    enterprise_name = models.CharField('企业名称', max_length=128, default='')
    phone = models.CharField('手机号', max_length=20, unique=True)
    # 申请时由用户自填密码，此处仅存哈希值。审核通过时直接复制到 auth_user.password。
    password = models.CharField('登录密码哈希', max_length=128, default='')
    reason = models.CharField('申请原因', max_length=200)
    status = models.CharField('审核状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='开通公司',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '账号申请'
        verbose_name_plural = '账号申请'

    def __str__(self) -> str:
        return f'{self.applicant_name} - {self.login_username}'

    @property
    def login_username(self) -> str:
        """返回审核通过后用于创建登录账号的用户名。"""
        return (self.username or self.phone).strip()

    def ensure_login_user(self):
        """确保已通过申请存在对应登录账号，兼容历史已通过但未建号的数据。

        用户的登录密码直接来自 AccountApplication.password（已经是哈希）。
        admin 想"看密码"=点用户详情页的"修改密码"链接重置一个新值（Django 自带）。
        """
        user = User.objects.filter(username=self.login_username).first()

        if user is None:
            user = User.objects.create(
                username=self.login_username,
                first_name=self.applicant_name,
                is_active=True,
            )
            # 直接复制已 hash 的 password；不要再次 set_password 否则会双重哈希。
            user.password = self.password
            user.save(update_fields=['password'])
            return user

        update_fields = []
        if user.first_name != self.applicant_name:
            user.first_name = self.applicant_name
            update_fields.append('first_name')
        if not user.is_active:
            user.is_active = True
            update_fields.append('is_active')
        # 已经存在的账号不强制覆盖密码，避免管理员手动改过的密码被申请记录里的旧 hash 还原。
        if update_fields:
            user.save(update_fields=update_fields)
        return user

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()

        super().save(*args, **kwargs)

        if self.status == self.STATUS_APPROVED:
            user = self.ensure_login_user()
            self.provision_company(user)
            return

        if previous_status == self.status:
            return

        user = User.objects.filter(username=self.login_username).first()
        if user is not None and user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])

    def provision_company(self, user):
        """审批通过后为申请人开通公司：建 Tenant + 把申请人设为公司管理员，并回写 self.tenant。

        幂等：provision_company 检测到已有 Membership 时直接复用，重复审批不会建出多家公司。
        用 .update() 回写避免再次触发 save() 递归。
        """
        # 懒加载避免 app 加载顺序问题（accounts ↔ tenants）。
        from apps.tenants.services import provision_company as _provision

        company_name = (self.enterprise_name or self.applicant_name or self.login_username).strip()
        tenant = _provision(name=company_name, admin_user=user)
        if self.tenant_id != tenant.id:
            self.tenant = tenant
            type(self).objects.filter(pk=self.pk).update(tenant=tenant)
        return tenant


class Menu(models.Model):
    AUDIENCE_ALL = 'all'
    AUDIENCE_PLATFORM = 'platform'
    AUDIENCE_TENANT_ADMIN = 'tenant_admin'
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, '通用业务菜单（可分配）'),
        (AUDIENCE_PLATFORM, '平台超管专属'),
        (AUDIENCE_TENANT_ADMIN, '公司管理员专属'),
    ]

    name = models.CharField('菜单名称', max_length=64)
    key = models.CharField('菜单键', max_length=128, unique=True)
    path = models.CharField('路由路径', max_length=128, unique=True)
    icon = models.CharField('图标', max_length=64, blank=True, default='')
    # 受众决定菜单归属：all=可被超管分配给公司、再由公司管理员分配给员工；
    # platform=仅超管（如租户管理）；tenant_admin=仅公司管理员（如员工管理），员工与可分配目录均不含。
    audience = models.CharField('菜单受众', max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name='父级菜单',
        blank=True,
        null=True,
    )
    sort_order = models.PositiveIntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = '菜单'
        verbose_name_plural = '菜单'

    def __str__(self) -> str:
        return f'{self.name} ({self.path})'


class PermissionPoint(models.Model):
    name = models.CharField('权限名称', max_length=64)
    code = models.CharField('权限编码', max_length=128, unique=True)
    module = models.CharField('所属模块', max_length=64)
    description = models.TextField('权限说明', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['module', 'code']
        verbose_name = '权限点'
        verbose_name_plural = '权限点'

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class Role(models.Model):
    name = models.CharField('角色名称', max_length=64)
    code = models.CharField('角色编码', max_length=64)
    description = models.TextField('角色说明', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    # tenant 为 null 表示平台模板（is_template=True）；非 null 表示某公司自建角色。
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='roles',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )
    is_template = models.BooleanField('平台模板', default=False)
    menus = models.ManyToManyField(Menu, blank=True, related_name='roles', verbose_name='菜单')
    permission_points = models.ManyToManyField(
        PermissionPoint,
        blank=True,
        related_name='roles',
        verbose_name='权限点',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = '角色'
        verbose_name_plural = '角色'
        constraints = [
            # 角色编码在公司内唯一（不同公司可同名）。平台模板 tenant=null，
            # Postgres 视多个 null 为相异，模板间唯一性由 seed 自行保证。
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_role_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class UserRole(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_binding',
        verbose_name='用户',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_bindings',
        verbose_name='角色',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['user_id']
        verbose_name = '用户角色绑定'
        verbose_name_plural = '用户角色绑定'

    def __str__(self) -> str:
        return f'{self.user} -> {self.role}'
