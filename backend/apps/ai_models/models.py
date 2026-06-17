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
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'LLM 供应商'
        verbose_name_plural = 'LLM 供应商'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name} ({self.get_provider_type_display()})'


class LLMModel(models.Model):
    provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.CASCADE,
        related_name='models',
        verbose_name='所属供应商',
    )
    name = models.CharField('真实模型名称', max_length=128)
    display_name = models.CharField('展示名称', max_length=128, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'name'], name='uniq_llm_model_provider_name'),
        ]

    def __str__(self):
        return self.display_name or self.name


class TenantLLMModelGrant(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='llm_model_grants',
        verbose_name='所属公司',
    )
    model = models.ForeignKey(
        LLMModel,
        on_delete=models.CASCADE,
        related_name='tenant_grants',
        verbose_name='授权模型',
    )
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'model'], name='uniq_tenant_llm_model_grant'),
        ]

    def __str__(self):
        return f'{self.tenant_id}:{self.model_id}'


class TenantLLMSettings(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='llm_settings',
        verbose_name='所属公司',
    )
    default_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_default_settings',
        verbose_name='默认模型',
    )
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    def __str__(self):
        return f'{self.tenant_id}:{self.default_model_id or "unset"}'


class LLMTestSettings(models.Model):
    test_prompt = models.TextField('测试提示词', default='请用一句中文回复：连接测试成功。')
    test_cooldown_seconds = models.PositiveIntegerField('测速冷却秒数', default=10)
    test_timeout_seconds = models.PositiveIntegerField('测速超时秒数', default=15)
    test_max_tokens = models.PositiveIntegerField('测速最大输出 Tokens', default=64)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return 'LLM Test Settings'

    @classmethod
    def load(cls) -> 'LLMTestSettings':
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


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


class TTSProvider(models.Model):
    code = models.CharField('供应商编码', max_length=32, unique=True, default='aliyun')
    name = models.CharField('供应商名称', max_length=128, default='阿里云 TTS')
    api_key = models.CharField('API Key', max_length=512, blank=True, default='')
    base_url = models.CharField('WebSocket URL', max_length=512, blank=True, default='')
    model = models.CharField('模型名称', max_length=128, blank=True, default='')
    default_voice = models.ForeignKey(
        'TTSVoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='默认音色',
    )
    sample_rate = models.PositiveIntegerField('采样率', default=24000)
    default_test_text = models.TextField(
        '默认测试文本',
        default='对吧~我就特别喜欢这种超市，尤其是过年的时候去逛超市就会觉得超级超级开心！想买好多好多的东西呢！',
    )
    is_active = models.BooleanField('是否启用', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'TTS 供应商'
        verbose_name_plural = 'TTS 供应商'
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.code})'

    @classmethod
    def load_aliyun(cls) -> 'TTSProvider':
        provider, _ = cls.objects.get_or_create(
            code='aliyun',
            defaults={
                'name': '阿里云 TTS',
                'api_key': getattr(settings, 'ALIYUN_TTS_API_KEY', ''),
                'base_url': getattr(settings, 'ALIYUN_TTS_BASE_URL', ''),
                'model': getattr(settings, 'ALIYUN_TTS_MODEL', ''),
                'sample_rate': getattr(settings, 'ALIYUN_TTS_SAMPLE_RATE', 24000),
                'default_test_text': getattr(settings, 'ALIYUN_TTS_DEFAULT_TEST_TEXT', ''),
                'is_active': True,
            },
        )
        return provider


class TTSVoice(models.Model):
    provider = models.ForeignKey(
        TTSProvider,
        on_delete=models.CASCADE,
        related_name='voices',
        verbose_name='所属供应商',
    )
    display_name = models.CharField('展示名称', max_length=128)
    voice_code = models.CharField('音色编码', max_length=128)
    gender = models.CharField('性别', max_length=16, blank=True, default='')
    avatar_path = models.CharField('头像路径', max_length=255, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    is_visible = models.BooleanField('是否展示', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = 'TTS 音色'
        verbose_name_plural = 'TTS 音色'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['provider', 'voice_code'], name='uniq_tts_voice_provider_code'),
        ]

    def __str__(self):
        return f'{self.display_name} ({self.voice_code})'


class TenantTTSSettings(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='tts_settings',
        verbose_name='所属公司',
    )
    default_voice = models.ForeignKey(
        TTSVoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_default_settings',
        verbose_name='默认音色',
    )
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '公司 TTS 设置'
        verbose_name_plural = '公司 TTS 设置'

    def __str__(self):
        return f'{self.tenant_id}:{self.default_voice_id or "unset"}'


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


def default_agent_opening_message(name: str) -> str:
    agent_name = (name or '智能体').strip() or '智能体'
    return f'你好，我是{agent_name}，很高兴见到你，有什么我可以帮你的吗？'


class AgentApplication(models.Model):
    """LLM-backed application configured with prompt and knowledge documents."""
    name = models.CharField('应用名称', max_length=128)
    description = models.CharField('应用说明', max_length=255, blank=True, default='')
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_applications',
        verbose_name='LLM 供应商',
    )
    llm_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_applications',
        verbose_name='LLM 模型',
    )
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    system_prompt = models.TextField('系统提示词', blank=True, default='')
    temperature = models.FloatField('Temperature', default=0.7)
    max_tokens = models.PositiveIntegerField('最大输出 Tokens', default=1000)
    opening_message_enabled = models.BooleanField('是否启用开场白', default=True)
    opening_message = models.TextField('开场白', blank=True, default='')
    suggested_questions = models.JSONField('建议问题', blank=True, default=list)
    voice_input_enabled = models.BooleanField('是否启用语音输入', default=False)
    reply_playback_enabled = models.BooleanField('是否自动播报回复', default=False)
    knowledge_documents = models.ManyToManyField(
        'knowledge_base.KnowledgeDocument',
        blank=True,
        related_name='agent_applications',
        verbose_name='绑定知识库文档',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_agent_applications',
        verbose_name='创建人',
        null=True,
        blank=True,
    )
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
        verbose_name = '智能体应用'
        verbose_name_plural = '智能体应用'
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_agent_application_name_per_tenant'),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.opening_message:
            self.opening_message = default_agent_opening_message(self.name)
        if self.llm_model:
            self.llm_provider = self.llm_model.provider
            self.model_name = self.llm_model.name
        else:
            self.llm_provider = None
            self.model_name = ''
        super().save(*args, **kwargs)


class AgentAnnotation(models.Model):
    """Exact-match standard reply for an agent application."""
    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        related_name='annotations',
        verbose_name='所属智能体',
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name='所属公司',
        null=True,
        blank=True,
    )
    question = models.CharField('标准问题', max_length=500)
    answer = models.TextField('标准回复')
    source_message = models.ForeignKey(
        'ChatMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='annotation_sources',
        verbose_name='来源助手消息',
    )
    is_active = models.BooleanField('是否启用', default=True)
    hit_count = models.PositiveIntegerField('命中次数', default=0)
    last_hit_at = models.DateTimeField('最近命中时间', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_agent_annotations',
        verbose_name='创建人',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '智能体标注'
        verbose_name_plural = '智能体标注'
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['application', 'question'],
                name='unique_agent_annotation_question_per_application',
            ),
        ]

    def __str__(self):
        return f'{self.application_id}: {self.question[:40]}'



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
    llm_model = models.ForeignKey(
        LLMModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='LLM 模型',
    )
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    summary = models.CharField('会话摘要', max_length=256, blank=True, default='')
    system_prompt = models.TextField('系统提示词', blank=True, default='')
    temperature = models.FloatField('Temperature', default=0.7)
    max_tokens = models.PositiveIntegerField('最大输出Tokens', default=1000)
    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='绑定应用',
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
        verbose_name = '聊天会话'
        verbose_name_plural = '聊天会话'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} ({self.user.username})'

    def save(self, *args, **kwargs):
        if self.llm_model:
            self.llm_provider = self.llm_model.provider
            self.model_name = self.llm_model.name
        else:
            self.llm_provider = None
            self.model_name = ''
        super().save(*args, **kwargs)



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
