[根目录](../AGENTS.md) > **backend**

# backend 模块 AGENTS.md

> 详细 FAQ 与历史变更见同目录 `CLAUDE.md`。本文件是 quick-ref。

## OVERVIEW

Django 5.2 + DRF + simplejwt + drf-spectacular + SimpleUI + Celery 5.5 + httpx 异步客户端 + uvicorn ASGI。

## STRUCTURE

```
backend/
├── apps/                # 业务 apps（每个一个 Django app）
│   ├── accounts/        # 登录 / JWT / 账号申请 / 权限 / 菜单
│   ├── ai_models/       # ASR/LLM/TTS 供应商 + 聊天会话（SSE 流式）
│   ├── admin_examples/  # SimpleUI 示例（参考用，不上线）
│   ├── devices/         # 数字人设备
│   ├── knowledge_base/  # 知识库文档（admin-only 状态维护）
│   └── resources/       # 图片/视频/滚动字幕/音色/模型/控制指令/点位
├── config/              # Django 项目配置（settings/celery/urls/exceptions/...）
├── common/              # 共享工具（当前为空目录）
├── media/               # 运行时上传产物（不入库的内容）
├── static/              # 项目自有静态资源
├── staticfiles/         # collectstatic 产物（包含 SimpleUI 厂商资源 1500+ 文件）
├── templates/           # admin 模板覆盖
├── manage.py            # 默认 DJANGO_SETTINGS_MODULE=config.settings.dev
└── requirements.txt
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 加 API | `apps/<app>/views.py` + `serializers.py` + `urls.py` → 注册到 `config/urls.py` |
| 加模型 | `apps/<app>/models.py` → `python manage.py makemigrations <app>` |
| 加后台页 | `apps/<app>/admin.py`（SimpleUI），分组/排序在 settings |
| 加 Celery 任务 | `apps/<app>/tasks.py` + `config/celery.py` autodiscover |
| 全局异常包络 | `config/exceptions.py` |
| 缓存管理 | `config/business_cache.py` + `/admin/cache/` 面板 |
| 运维面板 | `config/operations_admin.py` → `/admin/operations/` |
| settings 分层 | `config/settings/{base,dev,prod}.py`（base 是共同部分） |

## CONVENTIONS

- **App 标准布局**：`models.py` / `serializers.py` / `views.py` / `urls.py` / `admin.py` / `tasks.py`。**例外** `apps/resources/` 把"点位"独立成一组 `point_*.py`（同 app 内子领域，不拆 app）。
- **URL 注册**：所有业务 URL 都挂 `/api/v1/` 下；新 app 在 `config/urls.py` 加 `path('api/v1/', include('apps.<app>.urls'))`。
- **响应**：DRF view 默认成功返回业务数据 + 由 `config/exceptions.py` 拼成 `{status,message,data}`；**例外**：知识库下载（单文件 + bulk-download）返回原生二进制。
- **JWT**：`apps.accounts.permissions` 提供权限装饰器；菜单与权限由 `accounts` 在 `/auth/me/` 时注入响应。
- **SimpleUI 资源**：`staticfiles/admin/simpleui-x/**` 是 vendor，**不要手改**；要定制 admin 走 `templates/admin/` 或 `admin.py` 字段配置。
- **HTTP 客户端**：调上游 LLM / TTS 供应商一律 `httpx.AsyncClient`（`async def` 视图 + `StreamingHttpResponse` 异步生成器），不要回退 `requests`。

## ANTI-PATTERNS

- ❌ 同步 generator 包 `StreamingHttpResponse`：ASGI（uvicorn）下会被整段消费，浏览器看不到流。必须 `httpx.AsyncClient` + `async def` 生成器。
- ❌ SSE 解析只匹配 `data: `（带空格）：会丢 LongCat 的 `data:{...}`。统一用兼容正则。
- ❌ 在业务 API 里暴露知识库 `processing_status` 写入：首版硬边界，状态**只**走 `/admin/`。
- ❌ 在 `apps/resources/serializers.py` 给 `local_url` / `effective_url` 加可写字段：本地地址由 `views.py` 运行时基于 `model_file` 生成，永远只读。
- ❌ 在 compose 中把 DB/Redis 主机写成 `localhost`：要写服务名 `db` / `redis`。
- ❌ 把 admin 自定义页面的 view 直接挂到 `urls.py` 顶层：必须经过 `admin.site.admin_view(...)` 包裹，否则丢登录态保护（参考 `cache_admin` / `operations_admin`）。

## COMMANDS

```bash
# 开发
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py shell

# Celery（容器内推荐用 make backend-shell）
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# 种子
python manage.py seed_devices
python manage.py seed_operations_periodic_tasks

# 测试
python manage.py test apps.resources.tests
python manage.py test apps.<app>.tests.<module>
```

## NOTES

- 默认 settings = `config.settings.dev`；生产用 `config.settings.prod`，区别主要在 `DEBUG` / 静态文件托管 / `ALLOWED_HOSTS`。
- ASGI 入口 `config.asgi:application`；切到 wsgi 会破坏聊天室真实流式输出。
- `config/business_cache.py` 提供命名空间化的 Redis 缓存键工具，admin 缓存面板可清。
- `apps/admin_examples/` 仅为 SimpleUI 用法演示，**不**接入任何路由，迁移时可忽略。
- `apps/resources/point_*.py` 是控制点位的子领域（运行时 / 序列化器 / 后台 / 视图各一份），改动需要同时验证 `/commands/points/` 路由。
