from django.db import models
from django.db.models import Q

from apps.tenants.managers import TenantManager

# 复用的 tenant 外键定义：行级隔离，业务路径一律走 objects.for_tenant()。
def _tenant_fk():
    return models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )


class Resource(models.Model):
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_CHOICES = [
        (TYPE_IMAGE, '图片'),
        (TYPE_VIDEO, '视频'),
    ]

    CATEGORY_HORIZONTAL = 'horizontal'
    CATEGORY_VERTICAL = 'vertical'
    CATEGORY_UNCATEGORIZED = 'uncategorized'
    CATEGORY_CHOICES = [
        (CATEGORY_HORIZONTAL, '横屏'),
        (CATEGORY_VERTICAL, '竖屏'),
        (CATEGORY_UNCATEGORIZED, '未分类'),
    ]

    name = models.CharField('资源名称', max_length=128)
    resource_type = models.CharField('资源类型', max_length=20, choices=TYPE_CHOICES)
    category = models.CharField(
        '资源分类',
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_UNCATEGORIZED,
    )
    file = models.FileField('资源文件', upload_to='resources/%Y/%m/%d', blank=True, null=True)
    cloud_url = models.URLField('云端URL地址', max_length=2048, blank=True, default='')
    storage_backend = models.CharField('对象存储后端', max_length=32, blank=True, default='')
    object_key = models.CharField('MinIO 对象键', max_length=512, blank=True, default='')
    object_size = models.BigIntegerField('MinIO 对象大小', blank=True, null=True)
    description = models.CharField('资源说明', max_length=255, blank=True, default='')
    is_digital_human_background = models.BooleanField('是否作为数字人背景图', default=False)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = '资源（图片/视频）'
        verbose_name_plural = '资源（图片/视频）'

    def __str__(self) -> str:
        return f'{self.get_resource_type_display()} - {self.name}'

    @property
    def has_file(self) -> bool:
        return bool(self.file) or bool(self.object_key)


class ScrollingText(models.Model):
    I18N_SCHEME_ZH_EN = 'zh_en'
    I18N_SCHEME_CHOICES = [
        (I18N_SCHEME_ZH_EN, '中英'),
    ]

    title = models.CharField('标题', max_length=128)
    i18n_scheme = models.CharField('国际化方案', max_length=32, choices=I18N_SCHEME_CHOICES, default=I18N_SCHEME_ZH_EN)
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = '滚动文本'
        verbose_name_plural = '滚动文本'

    def __str__(self) -> str:
        return self.title


class ScrollingTextItem(models.Model):
    scrolling_text = models.ForeignKey(
        ScrollingText,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='滚动文本',
    )
    order = models.PositiveIntegerField('顺序')
    zh_text = models.TextField('中文文本')
    en_text = models.TextField('英文文本')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = '滚动文本明细'
        verbose_name_plural = '滚动文本明细'
        constraints = [
            models.UniqueConstraint(fields=['scrolling_text', 'order'], name='unique_scrolling_text_item_order'),
        ]

    def __str__(self) -> str:
        return f'{self.scrolling_text.title} #{self.order}'


class CommandGroup(models.Model):
    TYPE_CONTROL = 'control'
    TYPE_TASK = 'task'
    TYPE_CHOICES = [
        (TYPE_CONTROL, '控制指令'),
        (TYPE_TASK, '任务指令'),
    ]

    name = models.CharField('指令管理名称', max_length=128)
    group_type = models.CharField('指令类型', max_length=20, choices=TYPE_CHOICES)
    export_enabled = models.BooleanField('是否允许导出', default=False)
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['group_type', 'name', 'id']
        verbose_name = '指令分组'
        verbose_name_plural = '指令分组'

    def __str__(self) -> str:
        return f'{self.name} ({self.get_group_type_display()})'


class VoiceTone(models.Model):
    name = models.CharField('音色名称', max_length=128)
    voice_code = models.CharField('音色标识', max_length=128)
    content = models.TextField('ASR结果', blank=True, default='')
    icon = models.ImageField('音色图标', upload_to='voice-tones/icons/%Y/%m/%d', blank=True, null=True)
    audio = models.FileField('音色文件', upload_to='voice-tones/%Y/%m/%d', blank=True, null=True)
    is_active = models.BooleanField('是否启用', default=True)
    is_visible = models.BooleanField('前端可见', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = '音色'
        verbose_name_plural = '音色'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'voice_code'], name='unique_voice_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.voice_code})'

    @property
    def has_icon(self) -> bool:
        return bool(self.icon)

    @property
    def has_audio(self) -> bool:
        return bool(self.audio)


class ModelAsset(models.Model):
    TYPE_MALE = 'male'
    TYPE_FEMALE = 'female'
    TYPE_CHOICES = [
        (TYPE_MALE, '男'),
        (TYPE_FEMALE, '女'),
    ]

    ORIENTATION_HORIZONTAL = 'horizontal'
    ORIENTATION_VERTICAL = 'vertical'
    ORIENTATION_CHOICES = [
        (ORIENTATION_HORIZONTAL, '横屏'),
        (ORIENTATION_VERTICAL, '竖屏'),
    ]

    name = models.CharField('模型名称', max_length=128)
    model_type = models.CharField('模型类型', max_length=16, choices=TYPE_CHOICES)
    orientation = models.CharField('模型方向', max_length=16, choices=ORIENTATION_CHOICES)
    thumbnail = models.ImageField('模型缩略图', upload_to='models/thumbnails/%Y/%m/%d', blank=True, null=True)
    model_file = models.FileField('模型文件', upload_to='models/files/%Y/%m/%d', blank=True, null=True)
    model_size = models.BigIntegerField('模型大小(字节)', blank=True, null=True)
    cloud_url = models.URLField('云端地址', blank=True, default='')
    is_visible = models.BooleanField('前端可见', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = '模型管理'
        verbose_name_plural = '模型管理'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_model_asset_name_per_tenant'),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.model_file:
            try:
                self.model_size = self.model_file.size
            except OSError:
                self.model_size = None
        else:
            self.model_size = None
        super().save(*args, **kwargs)

    @property
    def has_thumbnail(self) -> bool:
        return bool(self.thumbnail)

    @property
    def has_model_file(self) -> bool:
        return bool(self.model_file)


class ControlCommand(models.Model):
    PROTOCOL_UDP = 'UDP'
    PROTOCOL_TCP = 'TCP'
    COMMAND_VALUE_TYPE_STRING = 'string'
    COMMAND_VALUE_TYPE_HEX = 'hex'
    COMMAND_VALUE_TYPE_ASCII = 'ascii'
    PROTOCOL_CHOICES = [
        (PROTOCOL_UDP, 'UDP'),
        (PROTOCOL_TCP, 'TCP'),
    ]
    COMMAND_VALUE_TYPE_CHOICES = [
        (COMMAND_VALUE_TYPE_STRING, '字符串'),
        (COMMAND_VALUE_TYPE_HEX, '16进制'),
        (COMMAND_VALUE_TYPE_ASCII, 'ascii'),
    ]

    group = models.ForeignKey(
        CommandGroup,
        on_delete=models.CASCADE,
        related_name='control_commands',
        verbose_name='所属指令分组',
        blank=True,
        null=True,
    )
    name = models.CharField('名称', max_length=128)
    command_code = models.CharField('指令', max_length=128)
    command_value_type = models.CharField('指令类型', max_length=16, choices=COMMAND_VALUE_TYPE_CHOICES, default=COMMAND_VALUE_TYPE_STRING)
    protocol = models.CharField('调用方式', max_length=16, choices=PROTOCOL_CHOICES, default=PROTOCOL_UDP)
    host = models.GenericIPAddressField('IP')
    port = models.PositiveIntegerField('端口')
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['group__name', 'name', 'id']
        verbose_name = '控制指令'
        verbose_name_plural = '控制指令'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'command_code'], name='unique_control_command_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.command_code})'


class TaskCommand(models.Model):
    group = models.ForeignKey(
        CommandGroup,
        on_delete=models.CASCADE,
        related_name='task_commands',
        verbose_name='所属指令分组',
        blank=True,
        null=True,
    )
    name = models.CharField('名称', max_length=128)
    command_code = models.CharField('指令', max_length=128)
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['group__name', 'name', 'id']
        verbose_name = '任务指令'
        verbose_name_plural = '任务指令'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'command_code'], name='unique_task_command_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.command_code})'


class TaskCommandStep(models.Model):
    TYPE_COMMAND = 'command'
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_NAVIGATION = 'navigation'
    TYPE_CHOICES = [
        (TYPE_COMMAND, '指令'),
        (TYPE_TEXT, '文本'),
        (TYPE_IMAGE, '图片'),
        (TYPE_VIDEO, '视频'),
        (TYPE_NAVIGATION, '导航指令'),
    ]

    task_command = models.ForeignKey(
        TaskCommand,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='任务指令',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='inner_tasks',
        verbose_name='上级导航子任务',
        blank=True,
        null=True,
    )
    order = models.PositiveIntegerField('顺序')
    task_type = models.CharField('子任务类型', max_length=20, choices=TYPE_CHOICES)
    control_command = models.ForeignKey(
        ControlCommand,
        on_delete=models.PROTECT,
        related_name='task_steps',
        verbose_name='控制指令',
        blank=True,
        null=True,
    )
    point = models.ForeignKey(
        'resources.Point',
        on_delete=models.PROTECT,
        related_name='task_steps',
        verbose_name='点位',
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name='task_steps',
        verbose_name='图片/视频资源',
        blank=True,
        null=True,
    )
    text_content = models.TextField('文本内容', blank=True, default='')
    image_text = models.TextField('图片子任务文本', blank=True, default='')
    delay_seconds = models.PositiveIntegerField('延迟时间（秒）', default=0)
    wait_for_inner_tasks = models.BooleanField('是否等待子子任务完成', default=False)
    is_show = models.BooleanField('是否显示到前端', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = '任务子任务'
        verbose_name_plural = '任务子任务'
        constraints = [
            models.UniqueConstraint(
                fields=['task_command', 'order'],
                condition=Q(parent__isnull=True),
                name='unique_task_command_root_step_order',
            ),
            models.UniqueConstraint(
                fields=['parent', 'order'],
                condition=Q(parent__isnull=False),
                name='unique_task_command_inner_step_order',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.task_command.command_code} #{self.order} {self.task_type}'


class MinioConfig(models.Model):
    STORAGE_BACKEND_LOCAL = 'local'
    STORAGE_BACKEND_R2 = 'r2'
    STORAGE_BACKEND_CHOICES = [
        (STORAGE_BACKEND_LOCAL, '现有方案'),
        (STORAGE_BACKEND_R2, 'R2 存储桶'),
    ]

    storage_backend = models.CharField('Active storage backend', max_length=32, choices=STORAGE_BACKEND_CHOICES, default=STORAGE_BACKEND_LOCAL)
    endpoint = models.CharField('Endpoint', max_length=255, blank=True, default='', help_text='host:port, e.g. localhost:9000')
    access_key = models.CharField('Access Key', max_length=255, blank=True, default='')
    secret_key = models.CharField('Secret Key', max_length=255, blank=True, default='')
    bucket_name = models.CharField('Bucket', max_length=255, blank=True, default='')
    secure = models.BooleanField('Use HTTPS', default=False)
    region = models.CharField('Region', max_length=64, blank=True, default='')
    public_base_url = models.URLField('Public base URL', max_length=512, blank=True, default='')
    r2_account_id = models.CharField('R2 Account ID', max_length=128, blank=True, default='')
    r2_access_key_id = models.CharField('R2 Access Key ID', max_length=255, blank=True, default='')
    r2_secret_access_key = models.CharField('R2 Secret Access Key', max_length=255, blank=True, default='')
    r2_bucket_name = models.CharField('R2 Bucket', max_length=255, blank=True, default='')
    r2_public_base_url = models.URLField('R2 Public base URL', max_length=512, blank=True, default='')
    video_max_size_mb = models.PositiveIntegerField('Video max size MB', default=1024)
    allow_video_cloud_url = models.BooleanField('Allow video cloud URL', default=True)
    is_active = models.BooleanField('Enable video direct upload', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'MinIO 配置'
        verbose_name_plural = 'MinIO 配置'

    def __str__(self) -> str:
        return f'MinIO Config ({self.bucket_name or "unset"})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def load(cls) -> 'MinioConfig':
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class TenantVideoQuota(models.Model):
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='video_quota')
    quota_mb = models.PositiveIntegerField('视频容量额度（MB）', blank=True, null=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '公司视频额度'
        verbose_name_plural = '公司视频额度'

    def __str__(self) -> str:
        return f'{self.tenant_id}: {self.quota_mb}MB' if self.quota_mb else f'{self.tenant_id}: unlimited'

    @property
    def quota_bytes(self) -> int:
        return int(self.quota_mb or 0) * 1024 * 1024


from .point_models import Point  # noqa: E402,F401
