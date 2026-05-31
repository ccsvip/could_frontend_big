from django.db import models

from apps.tenants.managers import TenantManager


class Point(models.Model):
    name = models.CharField('点位名称', max_length=128)
    command = models.CharField('点位命令', max_length=128)
    is_active = models.BooleanField('是否启用', default=True)
    is_show = models.BooleanField('是否显示到前端', default=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['command', 'id']
        verbose_name = '点位管理'
        verbose_name_plural = '点位管理'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'command'], name='unique_point_command_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.command})'
