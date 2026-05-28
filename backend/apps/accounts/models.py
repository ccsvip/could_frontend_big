from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()
DEFAULT_APPROVED_PASSWORD = '123456'


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
    phone = models.CharField('手机号', max_length=20, unique=True)
    email = models.EmailField('邮箱', blank=True)
    reason = models.CharField('申请原因', max_length=200)
    status = models.CharField('审核状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
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
        """确保已通过申请存在对应登录账号，兼容历史已通过但未建号的数据。"""
        user = User.objects.filter(username=self.login_username).first()

        if user is None:
            user = User.objects.create(
                username=self.login_username,
                email=self.email,
                first_name=self.applicant_name,
                is_active=True,
            )
            user.set_password(DEFAULT_APPROVED_PASSWORD)
            user.save(update_fields=['password'])
            return user

        update_fields = []
        if user.email != self.email:
            user.email = self.email
            update_fields.append('email')
        if user.first_name != self.applicant_name:
            user.first_name = self.applicant_name
            update_fields.append('first_name')
        if not user.is_active:
            user.is_active = True
            update_fields.append('is_active')
        if update_fields:
            user.save(update_fields=update_fields)
        return user

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()

        super().save(*args, **kwargs)

        if self.status == self.STATUS_APPROVED:
            self.ensure_login_user()
            return

        if previous_status == self.status:
            return

        user = User.objects.filter(username=self.login_username).first()
        if user is not None and user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])


class Menu(models.Model):
    name = models.CharField('菜单名称', max_length=64)
    key = models.CharField('菜单键', max_length=128, unique=True)
    path = models.CharField('路由路径', max_length=128, unique=True)
    icon = models.CharField('图标', max_length=64, blank=True, default='')
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
    code = models.CharField('角色编码', max_length=64, unique=True)
    description = models.TextField('角色说明', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
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
