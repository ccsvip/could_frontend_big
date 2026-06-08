from django.conf import settings
from django.db import models

from apps.tenants.managers import TenantManager


PROVIDER_TYPE_CHOICES = [
    ('openai', 'OpenAI'),
    ('gemini', 'Gemini'),
    ('claude', 'Claude'),
    ('kimi', 'Kimi'),
    ('doubao', '豆包'),
    ('deepseek', 'DeepSeek'),
    ('qwen', '通义千问'),
    ('zhipu', '智谱'),
    ('other', '其他'),
]


class LLMProvider(models.Model):
    name = models.CharField('供应商名称', max_length=128)
    provider_type = models.CharField('供应商类型', max_length=32, choices=PROVIDER_TYPE_CHOICES, default='openai')
    api_base_url = models.URLField('API 地址', max_length=512)
    api_key = models.CharField('API 密钥', max_length=512)
    avatar = models.ImageField('供应商头像', upload_to='ai_models/avatars/', blank=True, null=True)
    models_config = models.JSONField('模型列表', default=list, blank=True)
    is_active = models.BooleanField('是否启用', default=True)
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
        verbose_name = 'LLM 供应商'
        verbose_name_plural = 'LLM 供应商'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_provider_type_display()})'


class ASRConfig(models.Model):
    workspace_id = models.CharField('Workspace ID', max_length=128, blank=True, default='')
    api_key = models.CharField('API Key', max_length=512, blank=True, default='')
    base_url = models.CharField('WebSocket URL', max_length=512, blank=True, default='')
    model = models.CharField('模型名称', max_length=128, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'ASR 配置'
        verbose_name_plural = 'ASR 配置'

    def __str__(self):
        return f'ASR Config ({self.model or "unset"})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    @classmethod
    def load(cls) -> 'ASRConfig':
        instance, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'workspace_id': getattr(settings, 'MULTIMODAL_WORKSPACE_ID', ''),
                'api_key': getattr(settings, 'MULTIMODAL_API_KEY', ''),
                'base_url': getattr(settings, 'ASR_BASE_URL', ''),
                'model': getattr(settings, 'ASR_MODEL', ''),
                'is_active': True,
            },
        )
        return instance


class ASRReplacementRule(models.Model):
    source_text = models.CharField('原词', max_length=128)
    replacement_text = models.CharField('替换词', max_length=128)
    is_active = models.BooleanField('是否启用', default=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = 'ASR 替换词'
        verbose_name_plural = 'ASR 替换词'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'source_text'], name='uniq_asr_replacement_rule_tenant_source'),
        ]

    def __str__(self):
        return f'{self.source_text} -> {self.replacement_text}'


class ChatConversation(models.Model):
    """聊天会话"""
    title = models.CharField('会话标题', max_length=256, default='新对话')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations',
        verbose_name='所属用户',
    )
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='LLM 供应商',
    )
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    summary = models.CharField('会话摘要', max_length=256, blank=True, default='')
    system_prompt = models.TextField('系统提示词', blank=True, default='')
    temperature = models.FloatField('Temperature', default=0.7)
    max_tokens = models.PositiveIntegerField('最大输出Tokens', default=1000)
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
        verbose_name = '聊天会话'
        verbose_name_plural = '聊天会话'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} ({self.user.username})'


class ChatMessage(models.Model):
    """聊天消息"""
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_SYSTEM = 'system'
    ROLE_CHOICES = [
        (ROLE_USER, '用户'),
        (ROLE_ASSISTANT, '助手'),
        (ROLE_SYSTEM, '系统'),
    ]
    FEEDBACK_NONE = 'none'
    FEEDBACK_UP = 'up'
    FEEDBACK_DOWN = 'down'
    FEEDBACK_CHOICES = [
        (FEEDBACK_NONE, '未反馈'),
        (FEEDBACK_UP, '点赞'),
        (FEEDBACK_DOWN, '点踩'),
    ]

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='所属会话',
    )
    role = models.CharField('角色', max_length=16, choices=ROLE_CHOICES, default=ROLE_USER)
    content = models.TextField('消息内容')
    feedback = models.CharField('反馈', max_length=8, choices=FEEDBACK_CHOICES, default=FEEDBACK_NONE)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.get_role_display()}] {self.content[:50]}'
