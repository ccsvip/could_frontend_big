from django.db import models
from django.utils import timezone

from apps.tenants.managers import TenantManager


class Device(models.Model):
    STATUS_ONLINE = 'online'
    STATUS_OFFLINE = 'offline'
    STATUS_MAINTAINING = 'maintaining'
    STATUS_CHOICES = [
        (STATUS_ONLINE, '在线'),
        (STATUS_OFFLINE, '离线'),
        (STATUS_MAINTAINING, '维护中'),
    ]

    code = models.CharField('设备编号', max_length=32)
    name = models.CharField('设备名称', max_length=128)
    location = models.CharField('部署位置', max_length=128)
    status = models.CharField('运行状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_OFFLINE)
    last_heartbeat = models.DateTimeField('最近心跳', default=timezone.now)
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
        ordering = ['code']
        verbose_name = '设备'
        verbose_name_plural = '设备'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_device_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.code} - {self.name}'
