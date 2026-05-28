[根目录](./AGENTS.md)

# could_frontend - 项目根 AGENTS.md

> 模块级细节去看 [`web/AGENTS.md`](./web/AGENTS.md) 与 [`backend/AGENTS.md`](./backend/AGENTS.md)。本文件**只**讲根级 monorepo 协同（docker-compose 编排、端口映射、跨模块约定）。

## OVERVIEW

数字人后台管理平台（**solin**）：React 18 + Vite SPA（`web/`） + Django 5.2 + DRF + Celery + ASGI（`backend/`），由根 `docker-compose.yaml` 编排为 7 个容器。生产仓库名 `ai-human-server-frontend`，运行时容器前缀统一 `solin_`。

## STRUCTURE

```
could_frontend/
├── web/                  # React SPA（详见 web/AGENTS.md）
├── backend/              # Django + DRF + Celery（详见 backend/AGENTS.md）
├── docker-compose.yaml   # 7 服务：db / redis / backend / celery_worker / celery_beat / flower / web
└── .env                  # 仅声明宿主端口映射（**不**给容器内服务读）
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 改前端 | [`web/AGENTS.md`](./web/AGENTS.md) |
| 改后端 | [`backend/AGENTS.md`](./backend/AGENTS.md) |
| 改宿主端口 | 根 `.env` |
| 改容器内运行时变量 | `backend/.env`（DB / Redis / JWT / SECRET / 媒体）；`web/.env`（`VITE_API_BASE_URL` / `VITE_API_PROXY_TARGET`） |
| 加新服务 | `docker-compose.yaml` 注册到对应 `depends_on` 链路；DB/Redis/backend 用容器名而非 localhost |
| 新增镜像源 / 私有 PyPI | 根 `.env` 设 `APT_MIRROR` / `APT_SECURITY_MIRROR` / `PIP_INDEX_URL`，由 `x-backend-build` 锚点统一注入 |

## CONVENTIONS

- **双 .env 边界**：根 `.env` **只**有 `*_PORT`（宿主端口），不要塞业务变量；后端运行时配置全部进 `backend/.env`，前端进 `web/.env`。`docker-compose.yaml` 不会把根 `.env` 注入容器进程。
- **容器内主机名**：后端 / Celery 访问数据库写 `db`，访问缓存写 `redis`，前端代理目标写 `backend:8000`。**不要**用 `localhost`（编排网络下指向容器自身）。
- **重启策略统一**：所有服务 `restart: always`，依赖宿主或 docker daemon 重启后自动恢复。新增服务必须沿用。
- **构建锚点共用**：四个 backend 容器（backend / celery_worker / celery_beat / flower）共用 `x-backend-build` YAML 锚点；改 backend Dockerfile 一处，四个容器同步生效。
- **健康检查门禁**：`celery_worker` / `celery_beat` / `flower` / `web` 的 `depends_on` 都是 `backend: { condition: service_healthy }`，不是 `service_started`；backend healthcheck 走 8000 端口 TCP 探测。
- **宿主端口非默认**：见下表，**避免**与本机已有 Postgres / Redis / Vite 冲突。

## ANTI-PATTERNS

- ❌ 在 `docker-compose.yaml` 把 `DATABASE_URL` 写成 `postgres://...@localhost:5432/...`：必须 `db:5432`。
- ❌ 把业务变量加到根 `.env`：根只放宿主端口，容器进程读不到。
- ❌ 跳过 backend healthcheck 让 worker 直接启动：worker 启动命令含 `python manage.py migrate --check`，未迁移会立即退出循环重启。
- ❌ 在 `web` 容器里 `npm install` 后把 `node_modules` 同步出宿主：compose 已挂 `/app/node_modules` 匿名卷隔离，宿主侧若执行 `npm install` 应用宿主自己的版本，不要拷进去。
- ❌ 上线把 backend 启动命令的 `uvicorn config.asgi:application` 换成 `wsgi`：聊天室 SSE 流式会立即退化成阻塞返回（详 `backend/CLAUDE.md`）。
- ❌ 修改 backend 启动命令时丢掉 `seed_devices` / `seed_operations_periodic_tasks`：缺设备种子 + 周期任务，运维面板与设备列表会空。
- ❌ 修改 backend 启动命令时丢掉自动创建 superuser 的那段 inline shell：开发环境登录约定 `admin / admin123456`，丢了会卡 `/admin/` 入口。

## SERVICES & PORTS

| 服务 (容器名) | 镜像 / 构建 | 宿主端口 (.env) | 容器端口 | 依赖 |
|------|------|------|------|------|
| `solin_db` | postgres:16-alpine | `DB_PORT=5433` | 5432 | - |
| `solin_redis` | redis:7-alpine | `REDIS_PORT=6380` | 6379 | - |
| `solin_backend` | build `./backend` | `API_PORT=8880` | 8000 (uvicorn) | db, redis |
| `solin_celery_worker` | 同 backend | - | - | backend healthy |
| `solin_celery_beat` | 同 backend | - | - | backend healthy |
| `solin_flower` | 同 backend | `FLOWER_PORT=5555` | 5555 | backend healthy |
| `solin_web` | build `./web` | `WEB_PORT=5175` | 5173 (vite dev) | backend healthy |

## COMMANDS

```bash
# 一键起全栈（首次会构建镜像 + 自动迁移 + 创建 admin + 种子）
docker compose up -d

# 单独重建后端镜像（修了 requirements.txt / Dockerfile / settings 后必跑）
docker compose build backend && docker compose up -d backend celery_worker celery_beat flower

# 看后端日志（聊天室流式排障必备，关注 chat.send.* / chat.conversation.config_updated）
docker compose logs -f backend

# 进容器跑 manage.py / shell
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py test apps.resources.tests

# 前端本地（不入容器）
cd web && npm install && npm run dev
```

## NOTES

- 宿主端口刻意避开默认值（5432 → 5433、6379 → 6380、5173 → 5175、8000 → 8880），多项目并存不冲突；如果改回默认要同步 `web/.env` 的代理目标和后端 CORS 白名单。
- backend 容器启动序列固化在 compose `command:` inline shell：`migrate → seed_operations_periodic_tasks → collectstatic --noinput → 自动建 admin → seed_devices → uvicorn`。新增初始化步骤插这条链路里、不要另开 entrypoint 脚本。
- `web` 容器走 `npm run dev` + 挂载源码 + 匿名 `node_modules` 卷，**是开发态而非生产态**。生产部署需要另写一份 compose 或 Dockerfile 改成 `npm run build` + 静态托管。
- 国内镜像默认值：APT 走阿里云 Debian、PyPI 走清华 Tsinghua，由 `x-backend-build.args` 注入；离线 / 海外环境覆盖根 `.env` 即可。
- 子目录文档同时维护两份：`AGENTS.md`（quick-ref）+ `CLAUDE.md`（详细 FAQ + Changelog）。新增模块文档遵循同一对偶。
