from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import models


class KnowledgeDocument(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待审核'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已拒绝'),
    ]

    title = models.CharField('文档标题', max_length=255)
    file = models.FileField('文档文件', upload_to='knowledge-base/%Y/%m/%d')
    file_name = models.CharField('原始文件名', max_length=255, blank=True, default='')
    file_extension = models.CharField('文件扩展名', max_length=32, blank=True, default='')
    file_size = models.BigIntegerField('文件大小(字节)', blank=True, null=True)
    description = models.CharField('文档说明', max_length=255, blank=True, default='')
    processing_status = models.CharField('处理状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    processing_result = models.TextField('处理结果', blank=True, default='')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='knowledge_documents',
        verbose_name='上传人',
        blank=True,
        null=True,
    )
    download_count = models.PositiveIntegerField('下载次数', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = '知识库文档'
        verbose_name_plural = '知识库文档'

    def __str__(self) -> str:
        return self.title or self.file_name or f'知识库文档 {self.pk}'

    def save(self, *args, **kwargs):
        if self.file:
            original_name = Path(self.file.name).name
            self.file_name = original_name
            self.file_extension = Path(original_name).suffix.lower().lstrip('.')
            try:
                self.file_size = self.file.size
            except OSError:
                self.file_size = None
            if not self.title:
                self.title = Path(original_name).stem
        else:
            self.file_name = ''
            self.file_extension = ''
            self.file_size = None
        super().save(*args, **kwargs)

