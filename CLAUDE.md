[根目录](./CLAUDE.md)

# could_frontend - 项目根 CLAUDE

> 模块级 FAQ 见 [`web/CLAUDE.md`](./web/CLAUDE.md) 与 [`backend/CLAUDE.md`](./backend/CLAUDE.md)。本文件只覆盖**根级**协同问题（compose 编排、端口、跨模块联调）。

## 项目职责

`could_frontend/` 是数字人后台管理平台（**solin**）的全栈仓库根。包含：

- `web/`：后台管理 SPA（React 18 + Vite + Antd + Tailwind + Zustand），登录后管理设备、资源、知识库、AI 供应商和聊天工作台。
- `backend/`：Django 5.2 + DRF + simplejwt + drf-spectacular + SimpleUI 后台 + Celery 5.5 + httpx 异步客户端 + uvicorn ASGI 入口。
- `docker-compose.yaml`：6 容器编排（db、redis、backend、celery_worker、celery_beat、web）。Celery 监控走 Django admin →「任务执行结果」/「周期任务」（`django-celery-beat` + `django-celery-results`），**没有** flower 服务。

## 入口与启动

- 容器一键起：`docker compose up -d`（首次会构建镜像 + 自动迁移 + 创建 superuser `admin / admin123456` + 种子设备/周期任务）
- 后端独立调试：`docker compose exec backend python manage.py runserver`（仅排障用，不打开聊天 SSE 流式特性）
- 前端独立调试：`cd web && npm install && npm run dev`（vite 默认 5173，host 0.0.0.0）

## 对外接口

根级**不直接**暴露接口。所有 HTTP 入口都在子模块：

- `solin_backend` 暴露 `${API_PORT}:8000`，REST 前缀 `/api/v1/*`，admin 在 `/admin/`，OpenAPI 在 `/api/docs/`，媒体在 `/media/`，静态在 `/static/`。
- `solin_web` 暴露 `${WEB_PORT}:5173`，vite 开发态。
- Celery worker / beat **不**对外暴露端口，监控走 `/admin/django_celery_results/` 与 `/admin/django_celery_beat/`。

## 关键依赖与配置

- 容器栈：postgres:16-alpine、redis:7-alpine、Python 3 + Django + Celery（自构建）、Node + Vite（自构建）
- 配置：根 `.env`（**仅** 4 个宿主端口 `WEB_PORT`/`API_PORT`/`DB_PORT`/`REDIS_PORT`）、`backend/.env`（业务运行时变量）、`web/.env`（vite 构建/运行时变量）
- 构建参数：`APT_MIRROR` / `APT_SECURITY_MIRROR` / `PIP_INDEX_URL`（默认阿里云 Debian + 清华 PyPI），通过 `x-backend-build.args` 注入

## 数据模型

根级**没有**数据模型。详见：

- 后端：`backend/CLAUDE.md` ＞「数据模型」章节
- 前端类型：`web/CLAUDE.md` ＞「数据模型」章节

## 测试与质量

- 后端：`docker compose exec backend python manage.py test apps.<app>.tests`（覆盖 voice-tone / model-asset / admin-model-asset 等，详见 `backend/CLAUDE.md`）
- 前端：当前**未配置**测试运行器；改动靠 `npm run build`（含 `tsc -b` 严格类型检查）作为唯一质量门禁
- 全栈联调：起完 compose 后访问 `http://localhost:${WEB_PORT}` 走 admin/admin123456 登录后人工冒烟

## 常见问题 (FAQ)

- Q: `docker compose up -d` 后 `web` 容器一直重启？
  - A: 通常是 backend 还没 healthy。`web` 的 `depends_on` 是 `condition: service_healthy`，要等 backend 完成 `migrate → collectstatic → 建 admin → seed_devices → uvicorn 监听 8000` 全流程。看 `docker compose logs backend` 直到 `Uvicorn running on http://0.0.0.0:8000`。
- Q: 前端能访问到 backend 但媒体图片裂图？
  - A: DEV 模式 axios 拦截器会把 `backend:8000/media/...` 重写成同源 `/media/...`（详 `web/CLAUDE.md`）。如果你跨容器/反代加了别的前缀，要在 `src/api/client.ts` 同步规则。
- Q: 改了 `backend/requirements.txt` 但 `pip install` 没生效？
  - A: 必须 `docker compose build backend` 重建镜像；compose 把 `./backend:/app` 挂在源码上，但依赖装在镜像层，不挂载。
- Q: 修了 `backend/.env` 没生效？
  - A: `env_file` 在容器**启动**时读，不是热加载。`docker compose up -d backend` 重建容器（不必重建镜像）。
- Q: Celery 任务一直 PENDING？
  - A: 三看：① `solin_redis` 是不是起来了；② `CELERY_BROKER_URL` 写的是 `redis://redis:6379/0` 而不是 `localhost`；③ `solin_celery_worker` 容器是不是 healthy。`docker compose logs celery_worker` 通常能直接定位。
- Q: 我在宿主用 `localhost:5432` 连不上 PG，但容器里能连？
  - A: 宿主映射端口是 `${DB_PORT}=5433`（不是 5432）。宿主连接串是 `postgres://postgres:postgres@localhost:5433/...`；容器内连接串是 `postgres://postgres:postgres@db:5432/...`。
- Q: 我自己电脑没装 Docker，能跑吗？
  - A: 能，但要自己起 PG + Redis；后端走 `python manage.py runserver`、前端走 `npm run dev`，并把 `backend/.env` 的 `DATABASE_URL` / `CELERY_BROKER_URL` 改成 `localhost:5432` / `localhost:6379`。聊天室真流式仍然要 `uvicorn config.asgi:application` 启动后端，不要 `runserver`。
- Q: 第一次起容器后 `admin / admin123456` 登不上？
  - A: backend 启动 inline shell 里的自动建号语句必须执行成功；如果你改过启动命令并删了那段 `User.objects.create_superuser(...)`，自己进容器 `python manage.py createsuperuser`。
- Q: 我可以把宿主端口改回默认（5432/6379/5173/8000）吗？
  - A: 可以，但记得同步：① `web/.env` 的 `VITE_API_PROXY_TARGET`；② 后端 CORS / `ALLOWED_HOSTS`；③ 任何外部对接（Webhook / 反代）写死的 URL。

## 相关文件清单

- `docker-compose.yaml`
- `.env`
- `web/AGENTS.md` / `web/CLAUDE.md`
- `backend/AGENTS.md` / `backend/CLAUDE.md`
- `web/src/api/AGENTS.md`
- `web/src/views/AGENTS.md`
- `web/src/views/command-management/AGENTS.md`
- `backend/config/AGENTS.md`
- `backend/apps/accounts/AGENTS.md`
- `backend/apps/ai_models/AGENTS.md`
- `backend/apps/devices/AGENTS.md`
- `backend/apps/knowledge_base/AGENTS.md`
- `backend/apps/resources/AGENTS.md`

## 变更记录 (Changelog)

- 2026-05-28：初始化根级 AGENTS.md / CLAUDE.md，承接子模块 `[根目录](../AGENTS.md)` / `[根目录](../CLAUDE.md)` 的链接锚点；专注 compose 编排、端口映射、双 `.env` 边界与跨模块联调 FAQ，不重复子模块内容。
- 2026-05-29：纠正容器栈描述（实际 6 容器，无 flower）、根 `.env` 端口数量（4 个：WEB/API/DB/REDIS_PORT），删除 `solin_flower` 入口表述；同步 `accounts` / `devices` / `knowledge_base` 子 AGENTS.md 链接。
