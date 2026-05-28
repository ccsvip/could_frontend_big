[backend](../AGENTS.md) > **config**

# backend/config AGENTS.md

## OVERVIEW

Django 项目根包。settings 三层 + Celery + ASGI/WSGI + URL 根 + 全局异常 + 自定义 admin 工具页。

## STRUCTURE

```
config/
├── settings/
│   ├── base.py           # 共享：INSTALLED_APPS, MIDDLEWARE, REST_FRAMEWORK, SIMPLEJWT, CELERY, STATIC/MEDIA
│   ├── dev.py            # DEBUG=True, 本地放宽
│   ├── prod.py           # DEBUG=False, ALLOWED_HOSTS / CSRF 严格
│   └── tests/            # 测试专用 settings（如有）
├── urls.py               # /api/v1/* 路由根 + admin/cache + admin/operations
├── asgi.py               # uvicorn 入口（聊天室真流式所必需）
├── wsgi.py               # 备份入口，不要默认用
├── celery.py             # Celery app + autodiscover
├── tasks.py              # config 级共享任务（不属于具体 app）
├── exceptions.py         # 全局 envelope（异常 → {status,message,data?}）
├── business_cache.py     # 命名空间化 Redis 缓存键工具
├── cache_admin.py        # /admin/cache/ 视图
└── operations_admin.py   # /admin/operations/ 视图（Celery+DB+Redis+beat 状态 + 任务投递）
```

## CONVENTIONS

- **settings 选择**：`DJANGO_SETTINGS_MODULE` 默认 `config.settings.dev`；生产由部署环境设置 `config.settings.prod`。**不要**在代码里硬编码引用具体子模块。
- **添加 app**：新 app 必须在 `settings/base.py` 的 `INSTALLED_APPS` 注册；URL 在 `urls.py` 用 `path('api/v1/', include('apps.<app>.urls'))` 加入。
- **异常包络**：自定义异常应继承标准 DRF 异常，由 `exceptions.custom_exception_handler` 自动转 envelope；**不要**在视图里手工 try/except 后 `Response({...})`，会破坏统一响应。
- **admin 自定义视图**：必须 `admin.site.admin_view(...)` 包裹；URL 注册放在 `admin.site.urls` 之前（否则会被 admin urls 截胡）。
- **Celery 队列**：默认队列单一；如需多队列，加在 `celery.py` 的 `task_routes` 而不是各 app 内零散 `apply_async(queue=...)`。

## ANTI-PATTERNS

- ❌ 在 `urls.py` 里手写 `/api/v1/auth/login/` 之类硬路径：用 `include('apps.<app>.urls')`。
- ❌ 修改 `ApiV1RootView` 时漏更新接口列表：它是 browsable API 入口，前端联调和外部对接都看这里。
- ❌ 在 `prod.py` 打开 `DEBUG=True`：除会泄露调试信息外，还会改变静态/媒体文件路径行为。
- ❌ 把 `business_cache.py` 的 key 直接 `cache.set()`：要走 `business_cache` 工具构造命名空间，否则 `/admin/cache/` 清理面板看不到。
- ❌ 在 `wsgi.py` 上线：聊天室必须 `asgi.py`（uvicorn）才能真流式。

## NOTES

- `STATIC_URL = '/static/'`、`STATIC_ROOT = BASE_DIR / 'staticfiles'`；`SERVE_LOCAL_STATIC` / `SERVE_LOCAL_MEDIA` 由 `.env` 控制是否在非 DEBUG 下让 Django 直接托管（通常生产由 nginx 接管）。
- `urls.py` 在 `DEBUG=True` 时通过 `static()` 自动挂 `/media`；非 DEBUG 仅当 `SERVE_LOCAL_MEDIA=True` 时挂上。
- `/admin/cache/` 与 `/admin/operations/` 都需要 `staff` 权限；后者额外限制为 superuser。
- `tasks.py` 当前主要用于运维型周期任务，会被 `seed_operations_periodic_tasks` 命令注册到 `django-celery-beat` 表。
