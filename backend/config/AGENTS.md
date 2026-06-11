[backend](../AGENTS.md) > **config**

# backend/config AGENTS.md

## OVERVIEW

Django 项目根包。settings 三层 + Celery + ASGI/WSGI + URL 根 + 全局异常 + 业务级 Redis 缓存工具。

## STRUCTURE

```
config/
├── settings/
│   ├── base.py           # 共享：INSTALLED_APPS, MIDDLEWARE, REST_FRAMEWORK, SIMPLEJWT, CELERY, STATIC/MEDIA
│   ├── dev.py            # DEBUG=True, 本地放宽
│   ├── prod.py           # DEBUG=False, ALLOWED_HOSTS / CSRF 严格
│   └── tests/            # 测试专用 settings（如有）
├── urls.py               # /api/v1/* 路由根
├── asgi.py               # uvicorn 入口（聊天流式接口所必需）
├── wsgi.py               # 备份入口，不要默认用
├── celery.py             # Celery app + autodiscover
├── tasks.py              # config 级共享任务（不属于具体 app）
├── exceptions.py         # 全局 envelope（异常 → {status,message,data?}）
└── business_cache.py     # 命名空间化 Redis 缓存键工具 + CachedBusinessResponseMixin
```

## CONVENTIONS

- **settings 选择**：`DJANGO_SETTINGS_MODULE` 默认 `config.settings.dev`；生产由部署环境设置 `config.settings.prod`。**不要**在代码里硬编码引用具体子模块。
- **添加 app**：新 app 必须在 `settings/base.py` 的 `INSTALLED_APPS` 注册；URL 在 `urls.py` 用 `path('api/v1/', include('apps.<app>.urls'))` 加入。
- **异常包络**：自定义异常应继承标准 DRF 异常，由 `exceptions.custom_exception_handler` 自动转 envelope；**不要**在视图里手工 try/except 后 `Response({...})`，会破坏统一响应。
- **业务缓存**：列表 / 详情接口加缓存请继承 `business_cache.CachedBusinessResponseMixin` 并设 `business_cache_namespace`，命名空间在 `BUSINESS_CACHE_NAMESPACES` 中预注册；**不要**直接 `cache.set()` 业务键，否则失去命名空间归属。
- **Celery 队列**：默认队列单一；如需多队列，加在 `celery.py` 的 `task_routes` 而不是各 app 内零散 `apply_async(queue=...)`。

## ANTI-PATTERNS

- ❌ 在 `urls.py` 里手写 `/api/v1/auth/login/` 之类硬路径：用 `include('apps.<app>.urls')`。
- ❌ 修改 `ApiV1RootView` 时漏更新接口列表：它是 browsable API 入口，前端联调和外部对接都看这里。
- ❌ 在 `prod.py` 打开 `DEBUG=True`：除会泄露调试信息外，还会改变静态/媒体文件路径行为。
- ❌ 绕过 `business_cache` 直接 `cache.set()` 业务数据：丢命名空间，跨进程清理失效。
- ❌ 在 `wsgi.py` 上线：聊天流式接口必须 `asgi.py`（uvicorn）才能真流式。

## NOTES

- `STATIC_URL = '/static/'`、`STATIC_ROOT = BASE_DIR / 'staticfiles'`；`SERVE_LOCAL_STATIC` / `SERVE_LOCAL_MEDIA` 由 `.env` 控制是否在非 DEBUG 下让 Django 直接托管（通常生产由 nginx 接管）。
- `urls.py` 在 `DEBUG=True` 时通过 `static()` 自动挂 `/media`；非 DEBUG 仅当 `SERVE_LOCAL_MEDIA=True` 时挂上。
- `BUSINESS_CACHE_ENABLED` / `BUSINESS_CACHE_TIMEOUT_SECONDS` 由 `backend/.env` 控制；命名空间清理走 `business_cache.clear_business_cache_namespace()`。
- `tasks.py` 当前主要用于运维型周期任务，会被 `seed_operations_periodic_tasks` 命令注册到 `django-celery-beat` 表。Django admin 的「周期任务」「任务执行结果」页面（由 `django-celery-beat` / `django-celery-results` 自动注册）替代了原先自研的 `/admin/operations/` 面板。
