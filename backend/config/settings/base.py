import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

import sentry_sdk
from config.sentry import before_send

sentry_sdk.init(
    dsn="https://9fc7401da3edadaa479d986c8584c939@o4507569064640512.ingest.us.sentry.io/4511515819638784",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    before_send=before_send,
)

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / '.env'

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',') if host.strip()]

INSTALLED_APPS = [
    'corsheaders',
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'django_celery_beat',
    'django_celery_results',
    'apps.accounts',
    'apps.tenants',
    'apps.devices',
    'apps.resources',
    'apps.knowledge_base',
    'apps.ai_models',
    'apps.audit',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 放在 AuthenticationMiddleware 之后：响应阶段 request.user 已就绪，便于审计解析操作人。
    'apps.audit.middleware.OperationLogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ImproperlyConfigured('DATABASE_URL must be set in backend/.env or the process environment.')

DATABASES = {
    'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
}

# 默认缓存必须走 Redis，保证 backend 与 Celery worker 进程共享同一份缓存数据。
REDIS_CACHE_URL = os.getenv('REDIS_CACHE_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_CACHE_URL,
    }
}
BUSINESS_CACHE_ENABLED = os.getenv('BUSINESS_CACHE_ENABLED', '1') == '1'
BUSINESS_CACHE_TIMEOUT_SECONDS = int(os.getenv('BUSINESS_CACHE_TIMEOUT_SECONDS', '300'))

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 兼容开发环境已创建的 md5 密码；登录成功后 Django 会升级为首选的 PBKDF2 哈希。
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
SERVE_LOCAL_STATIC = os.getenv('DJANGO_SERVE_LOCAL_STATIC', '0') == '1'
# 额外的静态文件源目录（开发环境直接读取，生产环境通过 collectstatic 收集到 STATIC_ROOT）
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
SERVE_LOCAL_MEDIA = os.getenv('DJANGO_SERVE_LOCAL_MEDIA', '0') == '1'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.StandardPageNumberPagination',
    'PAGE_SIZE': 10,
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '30'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Digital Human Admin API',
    'DESCRIPTION': '数字人管理平台后端接口文档',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'filter': True,
    },
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
    'SECURITY': [{'BearerAuth': []}],
    'ENUM_NAME_OVERRIDES': {
        'AccountApplicationStatusEnum': 'apps.accounts.models.AccountApplication.STATUS_CHOICES',
        'DeviceStatusEnum': 'apps.devices.models.Device.STATUS_CHOICES',
    },
}

# CORS 配置 - 开发环境允许本地端口
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://localhost:517\d$',
    r'^http://127\.0\.0\.1:517\d$',
]

# 生产环境 CORS 配置 - 允许所有来源（如需限制请修改）
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'True') == 'True'

# 如果不使用 CORS_ALLOW_ALL_ORIGINS，可以配置具体的允许来源
# CORS_ALLOWED_ORIGINS = [
#     'https://your-domain.com',
#     'http://your-server-ip',
# ]

# CORS 允许携带凭证
CORS_ALLOW_CREDENTIALS = True

# CSRF 信任的来源
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/1'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'django-db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

SIMPLEUI_CONFIG = {
    'system_keep': True,
    'menu_display': ['系统管理', '账号管理', '设备管理', '资源管理', '知识库', 'AI大模型', '系统工具'],
    'menus': [
        {
            'name': '系统工具',
            'icon': 'fas fa-tools',
            'models': [
                {
                    'name': '周期任务',
                    'icon': 'fas fa-clock',
                    'url': '/admin/django_celery_beat/periodictask/',
                },
                {
                    'name': 'Crontab 调度',
                    'icon': 'fas fa-calendar-alt',
                    'url': '/admin/django_celery_beat/crontabschedule/',
                },
                {
                    'name': '间隔调度',
                    'icon': 'fas fa-stopwatch',
                    'url': '/admin/django_celery_beat/intervalschedule/',
                },
                {
                    'name': '任务执行结果',
                    'icon': 'fas fa-tasks',
                    'url': '/admin/django_celery_results/taskresult/',
                },
                {
                    'name': '任务组结果',
                    'icon': 'fas fa-layer-group',
                    'url': '/admin/django_celery_results/groupresult/',
                },
            ],
        },
    ],
}


SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False

# ===== SimpleUI 自定义外观 =====
# 左上角 Logo（登录后顶部显示），需为可访问的静态资源 URL
SIMPLEUI_LOGO = '/static/admin/img/logo.png'
# 登录页粒子背景动画（True 开启 / False 关闭）
SIMPLEUI_LOGIN_PARTICLES = True
# 默认主题（可选：admin.lte.css/element.css/edition.lte.css 等，详见 SimpleUI 文档）
# SIMPLEUI_DEFAULT_THEME = 'admin.lte.css'
# 关闭 SimpleUI 自身的版本检查与启动信息收集
SIMPLEUI_LOADING = True

MULTIMODAL_WORKSPACE_ID = os.getenv('MULTIMODAL_WORKSPACE_ID', '').strip()
MULTIMODAL_API_KEY = os.getenv('MULTIMODAL_API_KEY', '').strip()
ASR_BASE_URL = os.getenv('ASR_BASE_URL', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime').strip()
ASR_MODEL = os.getenv('ASR_MODEL', 'qwen3-asr-flash-realtime').strip()
ALIYUN_MM_APP_ID = os.getenv('ALIYUN_MM_APP_ID', '').strip()
ALIYUN_MM_DOMAIN_CODE = os.getenv('ALIYUN_MM_DOMAIN_CODE', '').strip()
ALIYUN_MM_ACCESS_KEY_ID = os.getenv('ALIYUN_MM_ACCESS_KEY_ID', '').strip()
ALIYUN_MM_ACCESS_KEY_SECRET = os.getenv('ALIYUN_MM_ACCESS_KEY_SECRET', '').strip()
ALIYUN_MM_REGION = os.getenv('ALIYUN_MM_REGION', 'cn-beijing').strip() or 'cn-beijing'
ALIYUN_MM_ENDPOINT = (
    os.getenv('ALIYUN_MM_ENDPOINT', '').strip()
    or f'https://sfmmultimodalapp.{ALIYUN_MM_REGION}.aliyuncs.com'
)
ALIYUN_MM_API_VERSION = os.getenv('ALIYUN_MM_API_VERSION', '2025-09-09').strip() or '2025-09-09'
ALIYUN_MM_LIST_TOOLS_ACTION = os.getenv('ALIYUN_MM_LIST_TOOLS_ACTION', 'ListCommand').strip() or 'ListCommand'
ALIYUN_MM_TIMEOUT_SECONDS = float(os.getenv('ALIYUN_MM_TIMEOUT_SECONDS', '15'))

# 飞书自定义机器人 Webhook 配置（用于控制指令变更通知等场景）
# 在飞书群里 -> 设置 -> 群机器人 -> 添加机器人 -> 自定义机器人 中获取 webhook 地址。
# 若启用了「签名校验」安全策略，需要同时配置 FEISHU_WEBHOOK_SECRET。
FEISHU_WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK_URL', '').strip()
FEISHU_WEBHOOK_SECRET = os.getenv('FEISHU_WEBHOOK_SECRET', '').strip()
HOST_IP = os.getenv('HOST_IP', '').strip()
FEISHU_SERVER_IP = os.getenv('FEISHU_SERVER_IP', os.getenv('SERVER_IP', '')).strip()
