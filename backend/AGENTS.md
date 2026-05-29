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
| 业务列表/详情缓存 | 继承 `config/business_cache.py` 的 `CachedBusinessResponseMixin` |
| 周期任务 / 任务结果 | Django admin → 系统工具 →「周期任务」「任务执行结果」（由 `django-celery-beat` / `django-celery-results` 提供） |
| settings 分层 | `config/settings/{base,dev,prod}.py`（base 是共同部分） |
| 账号 / 权限 / 菜单 | [`apps/accounts/AGENTS.md`](./apps/accounts/AGENTS.md) |
| 设备与启动种子 | [`apps/devices/AGENTS.md`](./apps/devices/AGENTS.md) |
| 知识库下载 / 状态边界 | [`apps/knowledge_base/AGENTS.md`](./apps/knowledge_base/AGENTS.md) |
| AI 流式聊天 / 供应商 | [`apps/ai_models/AGENTS.md`](./apps/ai_models/AGENTS.md) |
| 资源 / 指令 / 点位 | [`apps/resources/AGENTS.md`](./apps/resources/AGENTS.md) |

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
- ❌ 把 admin 自定义页面的 view 直接挂到 `urls.py` 顶层：必须经过 `admin.site.admin_view(...)` 包裹，否则丢登录态保护。

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
- `config/business_cache.py` 提供命名空间化的 Redis 缓存键工具，业务 view 通过 `CachedBusinessResponseMixin` 复用；写穿要走命名空间，不要直接 `cache.set()`。
- `apps/resources/point_*.py` 是控制点位的子领域（运行时 / 序列化器 / 后台 / 视图各一份），改动需要同时验证 `/commands/points/` 路由。

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.