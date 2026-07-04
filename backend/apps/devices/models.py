from django.db import models
from django.utils import timezone

from apps.tenants.managers import TenantManager


def _tenant_fk():
    return models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )


class DeviceGroup(models.Model):
    name = models.CharField('分组名称', max_length=128)
    remark = models.CharField('备注', max_length=255, blank=True, default='')
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['name', 'id']
        verbose_name = '设备分组'
        verbose_name_plural = '设备分组'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_device_group_name_per_tenant'),
        ]

    def __str__(self) -> str:
        return self.name


class DeviceApplication(models.Model):
    name = models.CharField('应用名称', max_length=128)
    code = models.SlugField('应用标识', max_length=64)
    description = models.CharField('应用说明', max_length=255, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    agent_application = models.ForeignKey(
        'ai_models.AgentApplication',
        on_delete=models.SET_NULL,
        related_name='device_applications',
        verbose_name='绑定智能体',
        null=True,
        blank=True,
    )
    resources = models.ManyToManyField(
        'resources.Resource',
        blank=True,
        related_name='device_applications',
        verbose_name='图片/视频资源',
    )
    scrolling_texts = models.ManyToManyField(
        'resources.ScrollingText',
        blank=True,
        related_name='device_applications',
        verbose_name='滚动文本',
    )
    voice_tones = models.ManyToManyField(
        'resources.VoiceTone',
        blank=True,
        related_name='device_applications',
        verbose_name='音色',
    )
    tts_voices = models.ManyToManyField(
        'ai_models.TTSVoice',
        blank=True,
        related_name='device_applications',
        verbose_name='TTS 音色',
    )
    model_assets = models.ManyToManyField(
        'resources.ModelAsset',
        blank=True,
        related_name='device_applications',
        verbose_name='模型',
    )
    command_groups = models.ManyToManyField(
        'resources.CommandGroup',
        blank=True,
        related_name='device_applications',
        verbose_name='指令分组',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['name', 'id']
        verbose_name = '设备应用'
        verbose_name_plural = '设备应用'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='unique_device_application_code_per_tenant'),
        ]

    def __str__(self) -> str:
        return self.name


class Device(models.Model):
    STATUS_ONLINE = 'online'
    STATUS_OFFLINE = 'offline'
    AUTHORIZATION_PERMANENT = 'permanent'
    AUTHORIZATION_TRIAL = 'trial'
    STATUS_CHOICES = [
        (STATUS_ONLINE, '在线'),
        (STATUS_OFFLINE, '离线'),
    ]
    AUTHORIZATION_CHOICES = [
        (AUTHORIZATION_PERMANENT, '永久'),
        (AUTHORIZATION_TRIAL, '试用'),
    ]

    # code is the Android-generated unique device code.
    code = models.CharField('设备码', max_length=128, unique=True)
    name = models.CharField('设备名称', max_length=128)
    location = models.CharField('部署位置', max_length=128, blank=True, default='')
    status = models.CharField('设备状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_OFFLINE)
    application = models.ForeignKey(
        DeviceApplication,
        on_delete=models.SET_NULL,
        related_name='devices',
        verbose_name='绑定资源应用',
        null=True,
        blank=True,
    )
    agent_application = models.ForeignKey(
        'ai_models.AgentApplication',
        on_delete=models.SET_NULL,
        related_name='bound_devices',
        verbose_name='绑定智能体',
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        DeviceGroup,
        on_delete=models.SET_NULL,
        related_name='devices',
        verbose_name='设备分组',
        null=True,
        blank=True,
    )
    authorization_type = models.CharField(
        '授权类型',
        max_length=20,
        choices=AUTHORIZATION_CHOICES,
        default=AUTHORIZATION_PERMANENT,
    )
    expires_at = models.DateTimeField('到期时间', null=True, blank=True)
    software_version = models.CharField('软件版本', max_length=64, blank=True, default='')
    system_version = models.CharField('系统版本', max_length=128, blank=True, default='')
    mainboard_info = models.CharField('主板信息', max_length=255, blank=True, default='')
    is_enabled = models.BooleanField('是否启用', default=True)
    registered_at = models.DateTimeField('注册时间', null=True, blank=True)
    last_auth_at = models.DateTimeField('最后认证时间', null=True, blank=True)
    last_heartbeat = models.DateTimeField('最近心跳', null=True, blank=True)
    authorization_ignored_at = models.DateTimeField('授权请求忽略时间', null=True, blank=True)
    device_info = models.JSONField('设备信息', blank=True, default=dict)
    tenant = _tenant_fk()
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['code']
        verbose_name = '设备'
        verbose_name_plural = '设备'

    def __str__(self) -> str:
        return f'{self.code} - {self.name}'

    @property
    def effective_agent_application(self):
        if self.agent_application_id:
            return self.agent_application
        application = getattr(self, 'application', None)
        return getattr(application, 'agent_application', None)

    @property
    def is_expired(self) -> bool:
        return self.authorization_type == self.AUTHORIZATION_TRIAL and bool(self.expires_at and self.expires_at <= timezone.now())


class WakeWord(models.Model):
    text = models.CharField('唤醒词', max_length=16)
    encoded_text = models.CharField('编码后唤醒词', max_length=255)
    boost = models.DecimalField('增强分数', max_digits=4, decimal_places=2, default=2.0)
    threshold = models.DecimalField('触发阈值', max_digits=4, decimal_places=2, default=0.25)
    is_active = models.BooleanField('是否启用', default=True)
    tenant = _tenant_fk()
    devices = models.ManyToManyField(
        Device,
        blank=True,
        related_name='wake_words',
        verbose_name='绑定设备',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['text', 'id']
        verbose_name = '唤醒词'
        verbose_name_plural = '唤醒词'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'text'], name='unique_wake_word_text_per_tenant'),
        ]

    def __str__(self) -> str:
        return self.text

    @staticmethod
    def _format_decimal(value) -> str:
        formatted = format(value, 'f').rstrip('0').rstrip('.') or '0'
        if '.' not in formatted:
            return f'{formatted}.0'
        return formatted

    @property
    def keyword_line(self) -> str:
        boost = self._format_decimal(self.boost)
        threshold = self._format_decimal(self.threshold)
        return f'{self.encoded_text} @{self.text} :{boost} #{threshold}'


class DeviceAuthorizationCode(models.Model):
    STATUS_UNUSED = 'unused'
    STATUS_USED = 'used'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_UNUSED, '未使用'),
        (STATUS_USED, '已使用'),
        (STATUS_DISABLED, '已禁用'),
    ]

    tenant = _tenant_fk()
    application = models.ForeignKey(
        DeviceApplication,
        on_delete=models.CASCADE,
        related_name='authorization_codes',
        verbose_name='绑定应用',
    )
    code = models.CharField('授权码', max_length=64, unique=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_UNUSED)
    authorization_type = models.CharField(
        '授权类型',
        max_length=20,
        choices=Device.AUTHORIZATION_CHOICES,
        default=Device.AUTHORIZATION_TRIAL,
    )
    expires_at = models.DateTimeField('到期时间', null=True, blank=True)
    used_at = models.DateTimeField('使用时间', null=True, blank=True)
    used_by_device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        related_name='authorization_codes',
        verbose_name='使用设备',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='创建人',
        null=True,
        blank=True,
    )
    remark = models.CharField('备注', max_length=255, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = '设备授权码'
        verbose_name_plural = '设备授权码'

    def __str__(self) -> str:
        return self.code

    @property
    def is_available(self) -> bool:
        if self.status != self.STATUS_UNUSED:
            return False
        return not (self.expires_at and self.expires_at <= timezone.now())


class DeviceAuthLog(models.Model):
    ACTION_ACTIVATE = 'activate'
    ACTION_HEARTBEAT = 'heartbeat'
    ACTION_CONFIG = 'config'
    ACTION_BIND = 'bind'
    ACTION_IGNORE = 'ignore'
    ACTION_AUTHORIZE = 'authorize'
    ACTION_REVOKE = 'revoke'
    ACTION_CHOICES = [
        (ACTION_ACTIVATE, '激活'),
        (ACTION_HEARTBEAT, '心跳'),
        (ACTION_CONFIG, '配置拉取'),
        (ACTION_BIND, '绑定'),
        (ACTION_IGNORE, '忽略'),
        (ACTION_AUTHORIZE, '再次授权'),
        (ACTION_REVOKE, '撤销授权'),
    ]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='+', null=True, blank=True)
    application = models.ForeignKey(DeviceApplication, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)
    agent_application = models.ForeignKey(
        'ai_models.AgentApplication',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='绑定智能体快照',
    )
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, related_name='auth_logs', null=True, blank=True)
    auth_code = models.ForeignKey(DeviceAuthorizationCode, on_delete=models.SET_NULL, related_name='auth_logs', null=True, blank=True)
    code = models.CharField('设备码', max_length=128, blank=True, default='')
    action = models.CharField('动作', max_length=32, choices=ACTION_CHOICES)
    result = models.BooleanField('结果', default=False)
    message = models.CharField('消息', max_length=255, blank=True, default='')
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    device_info = models.JSONField('设备信息', blank=True, default=dict)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = '设备授权日志'
        verbose_name_plural = '设备授权日志'

    def __str__(self) -> str:
        return f'{self.action}:{self.code}:{self.result}'


class DeviceChatLog(models.Model):
    SOURCE_HTTP = 'http'
    SOURCE_WEBSOCKET = 'websocket'
    SOURCE_CHOICES = [
        (SOURCE_HTTP, 'HTTP'),
        (SOURCE_WEBSOCKET, 'WebSocket'),
    ]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='+', null=True, blank=True)
    application = models.ForeignKey(DeviceApplication, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)
    agent_application = models.ForeignKey(
        'ai_models.AgentApplication',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='绑定智能体快照',
    )
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, related_name='chat_logs', null=True, blank=True)
    conversation = models.ForeignKey(
        'ai_models.ChatConversation',
        on_delete=models.SET_NULL,
        related_name='device_chat_logs',
        null=True,
        blank=True,
        verbose_name='智能体会话',
    )
    code = models.CharField('设备码', max_length=128, blank=True, default='')
    source = models.CharField('来源', max_length=32, choices=SOURCE_CHOICES)
    question_text = models.TextField('问题')
    answer_text = models.TextField('回答')
    answer_blocks = models.JSONField('回答内容块', blank=True, default=list)
    request_id = models.CharField('请求 ID', max_length=64, blank=True, default='')
    trace_id = models.CharField('链路 ID', max_length=64, blank=True, default='')
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = '设备对话日志'
        verbose_name_plural = '设备对话日志'

    def __str__(self) -> str:
        return f'{self.source}:{self.code}:{self.question_text[:30]}'
