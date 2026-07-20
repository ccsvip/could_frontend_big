from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


def generate_release_id() -> str:
    return f'release-{uuid.uuid4().hex}'


def app_release_upload_to(instance: 'AppRelease', filename: str) -> str:
    return f'app-updates/{instance.release_id}/{Path(filename).name}'


class AppRelease(models.Model):
    release_id = models.CharField('发布 ID', max_length=64, unique=True, default=generate_release_id, editable=False)
    package_name = models.CharField('应用包名', max_length=255, default='com.solin.digital')
    version_name = models.CharField('版本名称', max_length=64)
    version_code = models.PositiveBigIntegerField('内部版本号', unique=True)
    version_info = models.CharField('完整版本标识', max_length=255, unique=True)
    apk_file = models.FileField('APK 文件', upload_to=app_release_upload_to, max_length=512)
    file_name = models.CharField('原始文件名', max_length=255, editable=False)
    file_size = models.PositiveBigIntegerField('文件大小', editable=False)
    sha256 = models.CharField('SHA-256', max_length=64, editable=False)
    force_upgrade_version_code = models.PositiveBigIntegerField('强制升级阈值', default=0)
    release_notes = models.TextField('更新说明', blank=True, default='')
    is_active = models.BooleanField('启用', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_app_releases',
        verbose_name='创建人',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    IMMUTABLE_FIELDS = (
        'release_id',
        'package_name',
        'version_name',
        'version_code',
        'version_info',
        'apk_file',
        'file_name',
        'file_size',
        'sha256',
        'force_upgrade_version_code',
        'release_notes',
        'created_by_id',
    )

    class Meta:
        ordering = ['-version_code', '-id']
        verbose_name = '应用发布版本'
        verbose_name_plural = '应用发布版本'
        constraints = [
            models.CheckConstraint(condition=Q(version_code__gt=0), name='app_release_version_code_positive'),
            models.CheckConstraint(
                condition=Q(force_upgrade_version_code__lte=F('version_code')),
                name='app_release_force_threshold_lte_version',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.version_name} ({self.version_code})'

    def clean(self) -> None:
        super().clean()
        expected_package = getattr(settings, 'APP_UPDATE_PACKAGE_NAME', 'com.solin.digital')
        if self.package_name != expected_package:
            raise ValidationError({'package_name': f'应用包名必须为 {expected_package}'})
        if not self.apk_file:
            raise ValidationError({'apk_file': '请选择 APK 文件'})
        original_name = Path(self.apk_file.name).name
        if not original_name.lower().endswith('.apk'):
            raise ValidationError({'apk_file': '仅支持 .apk 文件'})
        expected_name = f'{self.version_info}.apk'
        if original_name != expected_name:
            raise ValidationError({'apk_file': f'APK 文件名必须为 {expected_name}'})
        if self.force_upgrade_version_code > self.version_code:
            raise ValidationError({'force_upgrade_version_code': '强制升级阈值不得高于目标版本号'})

    def _populate_file_metadata(self) -> None:
        self.file_name = Path(self.apk_file.name).name
        self.file_size = int(self.apk_file.size)
        digest = hashlib.sha256()
        if hasattr(self.apk_file, 'chunks'):
            for chunk in self.apk_file.chunks():
                digest.update(chunk)
        else:
            for chunk in iter(lambda: self.apk_file.read(1024 * 1024), b''):
                digest.update(chunk)
        self.apk_file.seek(0)
        self.sha256 = digest.hexdigest()

    def _validate_immutable(self) -> None:
        if not self.pk:
            return
        original = type(self).objects.get(pk=self.pk)
        changed = [field for field in self.IMMUTABLE_FIELDS if getattr(original, field) != getattr(self, field)]
        if changed:
            raise ValidationError('发布记录创建后仅允许修改启用状态')

    def save(self, *args, **kwargs) -> None:
        self._validate_immutable()
        self.full_clean(exclude=('file_name', 'file_size', 'sha256'))
        if not self.pk:
            self._populate_file_metadata()
        super().save(*args, **kwargs)


class AppUpdateEvent(models.Model):
    class State(models.TextChoices):
        UPDATE_AVAILABLE = 'UPDATE_AVAILABLE', '发现新版本'
        DOWNLOADING = 'DOWNLOADING', '开始下载'
        DOWNLOADED = 'DOWNLOADED', '下载完成'
        VERIFIED = 'VERIFIED', '校验成功'
        READY_TO_INSTALL = 'READY_TO_INSTALL', '等待安装'
        INSTALLING = 'INSTALLING', '提交安装'
        INSTALLED = 'INSTALLED', '安装成功'
        FAILED = 'FAILED', '失败'

    device = models.ForeignKey('devices.Device', on_delete=models.PROTECT, related_name='app_update_events')
    release = models.ForeignKey(AppRelease, on_delete=models.PROTECT, related_name='events')
    package_name = models.CharField('应用包名', max_length=255)
    current_version_code = models.PositiveBigIntegerField('更新前版本号')
    target_version_code = models.PositiveBigIntegerField('目标版本号')
    state = models.CharField('状态', max_length=32, choices=State.choices)
    message = models.TextField('补充信息', blank=True, default='')
    occurred_at = models.DateTimeField('客户端发生时间')
    created_at = models.DateTimeField('接收时间', auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = '应用升级事件'
        verbose_name_plural = '应用升级事件'
