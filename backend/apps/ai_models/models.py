from django.conf import settings
from django.db import models
from django.utils import timezone

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

RUNTIME_BACKEND_PLATFORM_LLM = 'platform_llm'
RUNTIME_BACKEND_THIRD_PARTY_CHATBOT = 'third_party_chatbot'
ASR_DEFAULT_EFFECTIVE_INPUT_TIMEOUT_SECONDS = 15
RUNTIME_BACKEND_CHOICES = [
    (RUNTIME_BACKEND_PLATFORM_LLM, '平台 LLM'),
    (RUNTIME_BACKEND_THIRD_PARTY_CHATBOT, '第三方会话机器人'),
]

THIRD_PARTY_PROVIDER_IHUAPENG = 'ihuapeng_chatbot'
THIRD_PARTY_PROVIDER_CONFIGURED_API = 'configured_api_chatbot'
THIRD_PARTY_PROVIDER_TYPE_CHOICES = [
    (THIRD_PARTY_PROVIDER_CONFIGURED_API, '配置化 API 机器人'),
    (THIRD_PARTY_PROVIDER_IHUAPENG, '华鹏会话机器人'),
]

THIRD_PARTY_CHATBOT_SCHEME_A = 'scheme_a'
THIRD_PARTY_CHATBOT_SCHEME_B = 'scheme_b'
THIRD_PARTY_CHATBOT_SCHEME_CHOICES = [
    (THIRD_PARTY_CHATBOT_SCHEME_A, '方案A'),
    (THIRD_PARTY_CHATBOT_SCHEME_B, '方案B'),
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
    enable_web_search = models.BooleanField('是否支持联网搜索', default=False)
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


class ThirdPartyChatbotProvider(models.Model):
    name = models.CharField('供应商名称', max_length=128)
    provider_type = models.CharField(
        '供应商类型',
        max_length=64,
        choices=THIRD_PARTY_PROVIDER_TYPE_CHOICES,
        default=THIRD_PARTY_PROVIDER_IHUAPENG,
    )
    api_base_url = models.URLField('API 地址', max_length=512)
    api_key = models.CharField('应用密钥', max_length=512)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '第三方会话机器人供应商'
        verbose_name_plural = '第三方会话机器人供应商'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name} ({self.get_provider_type_display()})'


class ThirdPartyChatbotApplication(models.Model):
    provider = models.ForeignKey(
        ThirdPartyChatbotProvider,
        on_delete=models.CASCADE,
        related_name='chatbots',
        verbose_name='所属供应商',
    )
    name = models.CharField('机器人名称', max_length=128)
    external_application_id = models.CharField('第三方应用 ID', max_length=128)
    description = models.CharField('机器人说明', max_length=255, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '第三方会话机器人'
        verbose_name_plural = '第三方会话机器人'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'external_application_id'],
                name='uniq_third_party_chatbot_provider_external_app',
            ),
        ]

    def __str__(self):
        return self.name


class TenantThirdPartyChatbotGrant(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='third_party_chatbot_grants',
        verbose_name='所属公司',
    )
    chatbot = models.ForeignKey(
        ThirdPartyChatbotApplication,
        on_delete=models.CASCADE,
        related_name='tenant_grants',
        verbose_name='授权机器人',
    )
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '公司第三方会话机器人授权'
        verbose_name_plural = '公司第三方会话机器人授权'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'chatbot'], name='uniq_tenant_third_party_chatbot_grant'),
        ]

    def __str__(self):
        return f'{self.tenant_id}:{self.chatbot_id}'


class ThirdPartyChatbotIntegration(models.Model):
    scheme_type = models.CharField(
        '方案类型',
        max_length=32,
        choices=THIRD_PARTY_CHATBOT_SCHEME_CHOICES,
        default=THIRD_PARTY_CHATBOT_SCHEME_A,
    )
    name = models.CharField('方案实例名称', max_length=128)
    remark = models.TextField('备注', blank=True, default='')
    provider = models.ForeignKey(
        ThirdPartyChatbotProvider,
        on_delete=models.CASCADE,
        related_name='integrations',
        verbose_name='第三方供应商',
    )
    chatbot = models.OneToOneField(
        ThirdPartyChatbotApplication,
        on_delete=models.CASCADE,
        related_name='integration',
        verbose_name='第三方机器人',
    )
    config = models.JSONField('API 流程配置', blank=True, default=dict)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '第三方会话机器人方案实例'
        verbose_name_plural = '第三方会话机器人方案实例'
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.name


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


class EmbeddingModel(models.Model):
    code = models.CharField('模型编码', max_length=32, unique=True, default='aliyun')
    name = models.CharField('模型名称', max_length=128, default='阿里云文本嵌入')
    api_key = models.CharField('API Key', max_length=512, blank=True, default='')
    base_url = models.CharField(
        '接口地址',
        max_length=512,
        blank=True,
        default='https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
    )
    model = models.CharField('DashScope 模型', max_length=128, blank=True, default='text-embedding-v4')
    dimensions = models.PositiveIntegerField('向量维度（0 表示模型默认）', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '嵌入模型'
        verbose_name_plural = '嵌入模型'
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.model or "unset"})'

    @classmethod
    def load_aliyun(cls) -> 'EmbeddingModel':
        defaults = {
            'name': '阿里云文本嵌入',
            'api_key': getattr(
                settings,
                'ALIYUN_EMBEDDING_API_KEY',
                getattr(settings, 'DASHSCOPE_API_KEY', getattr(settings, 'MULTIMODAL_API_KEY', '')),
            ),
            'base_url': getattr(
                settings,
                'ALIYUN_EMBEDDING_BASE_URL',
                'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
            ),
            'model': getattr(settings, 'ALIYUN_EMBEDDING_MODEL', 'text-embedding-v4'),
            'dimensions': getattr(settings, 'ALIYUN_EMBEDDING_DIMENSIONS', 0),
            'is_active': True,
        }
        provider, created = cls.objects.get_or_create(
            code='aliyun',
            defaults=defaults,
        )
        if not created:
            update_fields = []
            for field in ('api_key', 'base_url', 'model'):
                if not getattr(provider, field) and defaults[field]:
                    setattr(provider, field, defaults[field])
                    update_fields.append(field)
            if not provider.dimensions and defaults['dimensions']:
                provider.dimensions = defaults['dimensions']
                update_fields.append('dimensions')
            if update_fields:
                provider.save(update_fields=[*update_fields, 'updated_at'])
        return provider


class RerankModel(models.Model):
    code = models.CharField('模型编码', max_length=32, unique=True, default='aliyun')
    name = models.CharField('模型名称', max_length=128, default='阿里云文本重排序')
    api_key = models.CharField('API Key', max_length=512, blank=True, default='')
    base_url = models.CharField(
        '接口地址',
        max_length=512,
        blank=True,
        default='https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
    )
    model = models.CharField('DashScope 模型', max_length=128, blank=True, default='qwen3-vl-rerank')
    is_active = models.BooleanField('是否启用', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '重排序模型'
        verbose_name_plural = '重排序模型'
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ({self.model or "unset"})'

    @classmethod
    def load_aliyun(cls) -> 'RerankModel':
        defaults = {
            'name': '阿里云文本重排序',
            'api_key': getattr(
                settings,
                'ALIYUN_RERANK_API_KEY',
                getattr(settings, 'DASHSCOPE_API_KEY', getattr(settings, 'MULTIMODAL_API_KEY', '')),
            ),
            'base_url': getattr(
                settings,
                'ALIYUN_RERANK_BASE_URL',
                'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
            ),
            'model': getattr(settings, 'ALIYUN_RERANK_MODEL', 'qwen3-vl-rerank'),
            'is_active': True,
        }
        provider, created = cls.objects.get_or_create(
            code='aliyun',
            defaults=defaults,
        )
        if not created:
            update_fields = []
            for field in ('api_key', 'base_url', 'model'):
                if not getattr(provider, field) and defaults[field]:
                    setattr(provider, field, defaults[field])
                    update_fields.append(field)
            if update_fields:
                provider.save(update_fields=[*update_fields, 'updated_at'])
        return provider


class TenantKnowledgeModelSettings(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='knowledge_model_settings',
        verbose_name='所属公司',
    )
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_embedding_settings',
        verbose_name='嵌入模型',
    )
    rerank_model = models.ForeignKey(
        RerankModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_rerank_settings',
        verbose_name='重排序模型',
    )
    is_active = models.BooleanField('是否启用', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '公司知识库模型设置'
        verbose_name_plural = '公司知识库模型设置'

    def __str__(self):
        return f'{self.tenant_id}:embedding={self.embedding_model_id or "unset"};rerank={self.rerank_model_id or "unset"}'


class ASRConfig(models.Model):
    workspace_id = models.CharField('Workspace ID', max_length=128, blank=True, default='')
    api_key = models.CharField('API Key', max_length=512, blank=True, default='')
    base_url = models.CharField('WebSocket URL', max_length=512, blank=True, default='')
    model = models.CharField('模型名称', max_length=128, blank=True, default='')
    vad_threshold = models.FloatField('VAD检测阈值', default=0.0)
    vad_silence_duration_ms = models.PositiveIntegerField('VAD断句检测阈值(ms)', default=400)
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
                'vad_threshold': 0.0,
                'vad_silence_duration_ms': 400,
                'is_active': True,
            },
        )
        return instance


class ASRFillerWordSet(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='asr_filler_word_set',
        verbose_name='所属公司',
    )
    words_text = models.TextField('语气词', blank=True, default='')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '公司 ASR 语气词词表'
        verbose_name_plural = '公司 ASR 语气词词表'

    def __str__(self):
        return f'{self.tenant_id}: {self.words_text}'


class ASRRuntimeSettings(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='asr_runtime_settings',
        verbose_name='所属公司',
    )
    effective_input_timeout_seconds = models.PositiveSmallIntegerField(
        '有效输入等待上限（秒）',
        blank=True,
        null=True,
    )
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = '公司 ASR 运行时设置'
        verbose_name_plural = '公司 ASR 运行时设置'


def default_tts_session_config() -> dict:
    return {
        'mode': 'server_commit',
        'language_type': 'Auto',
        'response_format': 'pcm',
        'sample_rate': 24000,
        'speech_rate': 1.0,
        'volume': 50,
        'pitch_rate': 1.0,
        'bit_rate': 128,
        'instructions': '',
        'optimize_instructions': False,
    }


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
    tts_session_config = models.JSONField('TTS 会话配置', blank=True, default=default_tts_session_config)
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
                'tts_session_config': default_tts_session_config(),
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
    tts_session_config = models.JSONField('TTS 会话配置', blank=True, default=default_tts_session_config)
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


def default_agent_tts_session_config() -> dict:
    return default_tts_session_config()


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
    runtime_backend_type = models.CharField(
        '运行后端',
        max_length=32,
        choices=RUNTIME_BACKEND_CHOICES,
        default=RUNTIME_BACKEND_PLATFORM_LLM,
    )
    third_party_chatbot = models.ForeignKey(
        ThirdPartyChatbotApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_applications',
        verbose_name='第三方会话机器人',
    )
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    system_prompt = models.TextField('系统提示词', blank=True, default='')
    temperature = models.FloatField('Temperature', default=0.7)
    max_tokens = models.PositiveIntegerField('最大输出 Tokens', default=1000)
    max_tokens_unlimited = models.BooleanField('不限制最大输出 Tokens', default=False)
    opening_message_enabled = models.BooleanField('是否启用开场白', default=True)
    opening_message = models.TextField('开场白', blank=True, default='')
    suggested_questions = models.JSONField('建议问题', blank=True, default=list)
    voice_input_enabled = models.BooleanField('是否启用语音输入', default=False)
    reply_playback_enabled = models.BooleanField('是否自动播报回复', default=False)
    tts_filter_punctuation = models.CharField('TTS 过滤标点', max_length=64, blank=True, default='。！？!?；;、-')
    tts_filter_emoji = models.BooleanField('TTS 过滤表情', default=True)
    tts_filter_exclude_patterns = models.JSONField('TTS 排除文本', blank=True, default=list)
    knowledge_documents = models.ManyToManyField(
        'knowledge_base.KnowledgeDocument',
        blank=True,
        related_name='agent_applications',
        verbose_name='绑定知识库文档',
    )
    knowledge_bases = models.ManyToManyField(
        'knowledge_base.KnowledgeBase',
        blank=True,
        related_name='agent_applications',
        verbose_name='绑定知识库',
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
    published_config = models.JSONField('已发布配置', blank=True, default=dict)
    published_annotations = models.JSONField('已发布标注', blank=True, default=list)
    published_at = models.DateTimeField('发布时间', null=True, blank=True)
    published_version = models.PositiveIntegerField('发布版本', default=0)

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

    def build_publish_config(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'runtime_backend_type': self.runtime_backend_type or RUNTIME_BACKEND_PLATFORM_LLM,
            'llm_model_id': self.llm_model_id,
            'third_party_chatbot_id': self.third_party_chatbot_id,
            'system_prompt': self.system_prompt,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'max_tokens_unlimited': self.max_tokens_unlimited,
            'opening_message_enabled': self.opening_message_enabled,
            'opening_message': self.opening_message,
            'suggested_questions': list(self.suggested_questions or []),
            'voice_input_enabled': self.voice_input_enabled,
            'reply_playback_enabled': self.reply_playback_enabled,
            'tts_filter_punctuation': self.tts_filter_punctuation,
            'tts_filter_emoji': self.tts_filter_emoji,
            'tts_filter_exclude_patterns': list(self.tts_filter_exclude_patterns or []),
            'is_active': self.is_active,
            'knowledge_document_ids': list(self.knowledge_documents.order_by('id').values_list('id', flat=True)),
            'knowledge_base_ids': list(self.knowledge_bases.order_by('id').values_list('id', flat=True)),
        }

    def publish(self) -> None:
        from .services.reply_blocks import build_published_annotation_snapshot

        self.published_config = self.build_publish_config()
        self.published_annotations = build_published_annotation_snapshot(self)
        self.published_at = timezone.now()
        self.published_version = (self.published_version or 0) + 1
        self.save(update_fields=['published_config', 'published_annotations', 'published_at', 'published_version', 'updated_at'])

    def runtime_config(self) -> dict:
        config = self.published_config if self.published_at and self.published_config else self.build_publish_config()
        return {
            **config,
            'name': config.get('name', self.name),
            'description': config.get('description', self.description),
            'runtime_backend_type': config.get(
                'runtime_backend_type',
                self.runtime_backend_type or RUNTIME_BACKEND_PLATFORM_LLM,
            ),
            'llm_model_id': config.get('llm_model_id', self.llm_model_id),
            'third_party_chatbot_id': config.get('third_party_chatbot_id', self.third_party_chatbot_id),
            'system_prompt': config.get('system_prompt', self.system_prompt),
            'temperature': config.get('temperature', self.temperature),
            'max_tokens': config.get('max_tokens', self.max_tokens),
            'max_tokens_unlimited': config.get('max_tokens_unlimited', self.max_tokens_unlimited),
            'opening_message_enabled': config.get('opening_message_enabled', self.opening_message_enabled),
            'opening_message': config.get('opening_message', self.opening_message),
            'suggested_questions': config.get('suggested_questions', self.suggested_questions or []),
            'voice_input_enabled': config.get('voice_input_enabled', self.voice_input_enabled),
            'reply_playback_enabled': config.get('reply_playback_enabled', self.reply_playback_enabled),
            'tts_filter_punctuation': config.get('tts_filter_punctuation', self.tts_filter_punctuation),
            'tts_filter_emoji': config.get('tts_filter_emoji', self.tts_filter_emoji),
            'tts_filter_exclude_patterns': config.get('tts_filter_exclude_patterns', self.tts_filter_exclude_patterns or []),
            'is_active': config.get('is_active', self.is_active),
            'knowledge_document_ids': config.get('knowledge_document_ids', []),
            'knowledge_base_ids': config.get('knowledge_base_ids', []),
        }

    @property
    def is_published_current(self) -> bool:
        if not self.published_at or self.published_config != self.build_publish_config():
            return False
        from .services.reply_blocks import build_published_annotation_snapshot

        return self.published_annotations == build_published_annotation_snapshot(self)

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
    answer_blocks = models.JSONField('标准回复内容块', blank=True, default=list)
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
    runtime_backend_type = models.CharField(
        '运行后端',
        max_length=32,
        choices=RUNTIME_BACKEND_CHOICES,
        default=RUNTIME_BACKEND_PLATFORM_LLM,
    )
    third_party_chatbot = models.ForeignKey(
        ThirdPartyChatbotApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='第三方会话机器人',
    )
    external_session = models.JSONField('外部会话状态', blank=True, default=dict)
    model_name = models.CharField('模型名称', max_length=128, blank=True, default='')
    summary = models.CharField('会话摘要', max_length=256, blank=True, default='')
    system_prompt = models.TextField('系统提示词', blank=True, default='')
    temperature = models.FloatField('Temperature', default=0.7)
    max_tokens = models.PositiveIntegerField('最大输出Tokens', default=1000)
    max_tokens_unlimited = models.BooleanField('不限制最大输出Tokens', default=False)
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
    content_blocks = models.JSONField('消息内容块', blank=True, default=list)
    feedback = models.CharField('反馈', max_length=8, choices=FEEDBACK_CHOICES, default=FEEDBACK_NONE)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.get_role_display()}] {self.content[:50]}'
