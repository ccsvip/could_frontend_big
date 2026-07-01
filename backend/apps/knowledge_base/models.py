from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import models

from apps.tenants.managers import TenantManager


class KnowledgeBase(models.Model):
    name = models.CharField('知识库名称', max_length=128)
    description = models.CharField('知识库说明', max_length=255, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    chunk_size = models.PositiveSmallIntegerField('分块长度', default=500)
    chunk_overlap = models.PositiveSmallIntegerField('分块重叠', default=50)
    retrieval_top_n = models.PositiveSmallIntegerField('默认召回段数', default=5)
    retrieval_min_score = models.FloatField('向量最低相关度', default=0.2)
    media_max_assets = models.PositiveSmallIntegerField('配套素材召回上限', default=0)
    media_min_relevance = models.FloatField('配套素材最低相关度', default=0.22)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_knowledge_bases',
        verbose_name='创建人',
        blank=True,
        null=True,
    )
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
        ordering = ['-updated_at', '-id']
        verbose_name = '知识库'
        verbose_name_plural = '知识库'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_knowledge_base_tenant_name'),
        ]

    def __str__(self) -> str:
        return self.name


class KnowledgeDocument(models.Model):
    class IndexStatus(models.TextChoices):
        PENDING = 'pending', '待索引'
        INDEXING = 'indexing', '索引中'
        READY = 'ready', '已就绪'
        FAILED = 'failed', '索引失败'

    title = models.CharField('文档标题', max_length=255)
    file = models.FileField('文档文件', upload_to='knowledge-base/%Y/%m/%d')
    file_name = models.CharField('原始文件名', max_length=255, blank=True, default='')
    file_extension = models.CharField('文件扩展名', max_length=32, blank=True, default='')
    file_size = models.BigIntegerField('文件大小(字节)', blank=True, null=True)
    description = models.CharField('文档说明', max_length=255, blank=True, default='')
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.SET_NULL,
        related_name='documents',
        verbose_name='所属知识库',
        blank=True,
        null=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='knowledge_documents',
        verbose_name='上传人',
        blank=True,
        null=True,
    )
    download_count = models.PositiveIntegerField('下载次数', default=0)
    index_status = models.CharField(
        '索引状态',
        max_length=16,
        choices=IndexStatus.choices,
        default=IndexStatus.PENDING,
    )
    index_error = models.TextField('索引错误', blank=True, default='')
    indexed_at = models.DateTimeField('索引完成时间', blank=True, null=True)
    chunk_count = models.PositiveIntegerField('分块数量', default=0)
    index_model = models.CharField('索引模型', max_length=128, blank=True, default='')
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


class KnowledgeDocumentChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='所属知识库文档',
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )
    chunk_index = models.PositiveIntegerField('分块序号')
    content = models.TextField('分块内容')
    content_hash = models.CharField('内容哈希', max_length=64)
    embedding = models.JSONField('向量', blank=True, default=list)
    embedding_model = models.CharField('嵌入模型', max_length=128)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['document_id', 'chunk_index']
        verbose_name = '知识库文档分块'
        verbose_name_plural = '知识库文档分块'
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'embedding_model', 'chunk_index'],
                name='uniq_knowledge_chunk_document_model_index',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'document']),
            models.Index(fields=['document', 'embedding_model']),
        ]

    def __str__(self) -> str:
        return f'{self.document_id}:{self.chunk_index}'

    def save(self, *args, **kwargs):
        if self.document_id and self.tenant_id is None:
            self.tenant = self.document.tenant
        super().save(*args, **kwargs)


class KnowledgeMediaAsset(models.Model):
    class EmbeddingStatus(models.TextChoices):
        PENDING = 'pending', '待处理'
        PROCESSING = 'processing', '处理中'
        READY = 'ready', '已就绪'
        FAILED = 'failed', '处理失败'

    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='media_assets',
        verbose_name='所属知识库',
    )
    resource = models.ForeignKey(
        'resources.Resource',
        on_delete=models.SET_NULL,
        related_name='knowledge_media_assets',
        verbose_name='资源素材',
        null=True,
        blank=True,
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )
    resource_type = models.CharField('素材类型', max_length=20)
    resource_name = models.CharField('素材名称', max_length=128, blank=True, default='')
    keywords = models.CharField('关键词', max_length=255, blank=True, default='')
    description = models.CharField('说明', max_length=500, blank=True, default='')
    vlm_description = models.TextField('系统生成说明', blank=True, default='')
    vlm_keywords = models.CharField('系统生成关键词', max_length=500, blank=True, default='')
    description_embedding = models.JSONField('说明文本向量', blank=True, default=list)
    multimodal_embedding = models.JSONField('多模态向量', blank=True, default=list)
    embedding_status = models.CharField(
        '素材向量状态',
        max_length=16,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING,
    )
    embedding_error = models.TextField('素材向量错误', blank=True, default='')
    embedding_model = models.CharField('素材向量模型', max_length=128, blank=True, default='')
    embedding_processed_at = models.DateTimeField('素材向量处理时间', blank=True, null=True)
    is_enabled = models.BooleanField('是否启用', default=True)
    priority = models.IntegerField('优先级', default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_knowledge_media_assets',
        verbose_name='创建人',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-priority', '-updated_at', '-id']
        verbose_name = '知识库配套素材'
        verbose_name_plural = '知识库配套素材'
        constraints = [
            models.UniqueConstraint(fields=['knowledge_base', 'resource'], name='uniq_knowledge_media_asset_base_resource'),
        ]
        indexes = [
            models.Index(fields=['tenant', 'knowledge_base'], name='kma_tenant_base_idx'),
            models.Index(fields=['knowledge_base', 'is_enabled'], name='kma_base_enabled_idx'),
            models.Index(fields=['tenant', 'embedding_status'], name='kma_tenant_embed_status_idx'),
        ]

    def __str__(self) -> str:
        return self.resource_name or f'配套素材 {self.pk}'

    @property
    def is_missing(self) -> bool:
        return self.resource_id is None

    def save(self, *args, **kwargs):
        if self.knowledge_base_id and self.tenant_id is None:
            self.tenant = self.knowledge_base.tenant
        if self.resource_id:
            self.resource_type = self.resource.resource_type
            self.resource_name = self.resource.name
            if not self.description:
                category = self.resource.get_category_display() if self.resource.category else ''
                parts = [self.resource.name, category, self.resource.get_resource_type_display()]
                if self.resource.description:
                    parts.append(self.resource.description)
                self.description = ' '.join(part for part in parts if part)
        super().save(*args, **kwargs)
