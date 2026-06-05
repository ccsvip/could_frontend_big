from django.conf import settings
from django.db import models


class OperationLog(models.Model):
    """写操作审计日志。

    由 OperationLogMiddleware 在成功的写请求（POST/PUT/PATCH/DELETE）后自动落库。
    只记录元数据（谁、在哪家公司、对哪个 path 做了什么动作、HTTP 状态码与时间），
    绝不存储请求/响应正文，以免把密码、token、密钥写进日志。
    """

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = [
        (ACTION_CREATE, '新增'),
        (ACTION_UPDATE, '修改'),
        (ACTION_DELETE, '删除'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='操作人',
    )
    # 冗余用户名：用户被删除后 actor 置空，仍可凭此追溯是谁做的操作。
    actor_username = models.CharField('操作人用户名', max_length=150, blank=True)
    actor_display_name = models.CharField('操作人姓名', max_length=150, blank=True, default='')
    actor_role_name = models.CharField('操作人角色', max_length=64, blank=True, default='')
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='所属公司',
    )
    action = models.CharField('操作类型', max_length=16, choices=ACTION_CHOICES)
    method = models.CharField('请求方法', max_length=8)
    path = models.CharField('请求路径', max_length=512)
    description = models.CharField('操作说明', max_length=255, blank=True, default='')
    status_code = models.IntegerField('响应状态码')
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'

    def __str__(self) -> str:
        return f'{self.actor_username or "匿名"} {self.action} {self.path} [{self.status_code}]'
