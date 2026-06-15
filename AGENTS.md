[根目录](./AGENTS.md)

# could_frontend - 项目根 AGENTS.md

> 模块级细节去看 [`web/AGENTS.md`](./web/AGENTS.md) 与 [`backend/AGENTS.md`](./backend/AGENTS.md)。本文件**只**讲根级 monorepo 协同（docker-compose 编排、端口映射、跨模块约定）。

## OVERVIEW

数字人后台管理平台（**solin**）：React 18 + Vite SPA（`web/`） + Django 5.2 + DRF + Celery + ASGI（`backend/`），由根 `docker-compose.yaml` 编排为 6 个容器。生产仓库名 `ai-human-server-frontend`，运行时容器前缀统一 `solin_`。

## ENVIRONMENT MANDATE（硬约束 / 不可绕开）

> **本项目所有日常开发、调试、测试、运行命令一律通过 `docker compose` 执行。禁止任何形式的宿主裸跑。**
> 这条规则优先级高于一切便利性诉求；任何 PR / 文档 / 脚本如果让人在宿主直接跑 `npm` / `python` / `pytest`，视为违规。

| ✅ 允许 | ❌ 禁止 |
|------|------|
| `docker compose up -d` 起全栈 | 宿主直接 `npm run dev` / `vite` |
| `docker compose exec backend python manage.py test ...` | 宿主直接 `python manage.py runserver` / `pytest` |
| `docker compose exec backend python manage.py shell` | 宿主装 venv / conda 跑 Django |
| `docker compose exec web npm install <pkg>` / `npm run lint` | 宿主装 Node 直接 `npm install` 调试 |
| 宿主用 GUI 客户端**只读**连容器（`localhost:5433` / `localhost:6380`） | 宿主单独起 Postgres / Redis 服务进程 |

理由：
- 后端启动序列（`migrate → seed_operations_periodic_tasks → collectstatic → 建 admin → seed_devices → uvicorn`）固化在 compose `command:` inline shell，宿主跑不了。
- 容器内主机名（`db` / `redis` / `backend:8000`）与宿主网络不通，绕开 docker 必须改连接串，极易污染 `backend/.env` / `web/.env` 并提交。
- 健康检查、自动重启、依赖顺序、镜像源（APT / PyPI 国内镜像）由 compose 统一编排，宿主跑这层全部失效。
- 团队协作的前提是"克隆 + `docker compose up -d` 即跑"。任何隐式的宿主依赖（Node 版本 / Python 版本 / 系统库）都会破坏这条约定，必须在镜像里固化。

唯一例外：编辑器（VS Code / IDE）和 Git 客户端在宿主跑，**但它们只读改源码**，不启动任何服务进程。

## STRUCTURE

```
could_frontend/
├── web/                  # React SPA（详见 web/AGENTS.md）
├── backend/              # Django + DRF + Celery（详见 backend/AGENTS.md）
├── docker-compose.yaml   # 6 服务：db / redis / backend / celery_worker / celery_beat / web
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

- **Docker-only 执行面**：所有运行时命令（启动 / 测试 / 迁移 / 安装依赖 / 看日志 / 进 shell）一律走 `docker compose ...` 或 `docker compose exec <service> ...`。详见上文 ENVIRONMENT MANDATE。
- **安卓运行时无登录**：安卓端不登录后台、不拿后台 JWT，也不保存设备 token。运行时链路（含 ASR）只提交设备号 `deviceCode`；HTTP 请求优先用 `X-Device-Code` 请求头，后端按 `Device -> tenant` 解析公司上下文。
- **双 .env 边界**：根 `.env` **只**有 `*_PORT`（宿主端口），不要塞业务变量；后端运行时配置全部进 `backend/.env`，前端进 `web/.env`。`docker-compose.yaml` 不会把根 `.env` 注入容器进程。
- **容器内主机名**：后端 / Celery 访问数据库写 `db`，访问缓存写 `redis`，前端代理目标写 `backend:8000`。**不要**用 `localhost`（编排网络下指向容器自身）。
- **重启策略统一**：所有服务 `restart: always`，依赖宿主或 docker daemon 重启后自动恢复。新增服务必须沿用。
- **构建锚点共用**：三个 backend 容器（backend / celery_worker / celery_beat）共用 `x-backend-build` YAML 锚点；改 backend Dockerfile 一处，三个容器同步生效。
- **健康检查门禁**：`celery_worker` / `celery_beat` / `web` 的 `depends_on` 都是 `backend: { condition: service_healthy }`，不是 `service_started`；backend healthcheck 走 8000 端口 TCP 探测。
- **宿主端口非默认**：见下表，**避免**与本机已有 Postgres / Redis / Vite 冲突。

## ANTI-PATTERNS

- ❌ 在 `docker-compose.yaml` 把 `DATABASE_URL` 写成 `postgres://...@localhost:5432/...`：必须 `db:5432`。
- ❌ 把业务变量加到根 `.env`：根只放宿主端口，容器进程读不到。
- ❌ 跳过 backend healthcheck 让 worker 直接启动：worker 启动命令含 `python manage.py migrate --check`，未迁移会立即退出循环重启。
- ❌ 在宿主跑 `npm install` / `npm run dev` 调试前端：违反 ENVIRONMENT MANDATE。`web` 容器已挂 `/app/node_modules` 匿名卷隔离依赖，宿主跑 `npm install` 既污染锁文件又跟容器版本漂移。装新依赖一律 `docker compose exec web npm install <pkg>`。
- ❌ 让安卓端登录后台、携带后台 JWT 或设备 token 调运行时 / ASR 接口：安卓没有后台账号体系，必须按 `deviceCode` 解析设备和公司。
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
| `solin_web` | build `./web` | `WEB_PORT=5175` | 5173 (vite dev) | backend healthy |

## UNDERSTAND ANYTHING（AI 代码理解辅助）

本仓库允许使用 `understand-anything` 辅助 AI 理解代码结构。它会在根目录 `.understand-anything/` 下生成知识图谱，用于描述文件、函数、类、模块、接口、配置、服务以及它们之间的 `imports` / `calls` / `depends_on` / `configures` 等关系。

使用原则：
- 当任务涉及陌生模块、跨前后端链路、权限/路由/API/状态流转、Celery/配置/部署影响面时，AI 应优先基于 Understand Anything 做结构理解，再修改代码。
- 小型、明确、单文件修复可以直接读源码；不要为了 trivial change 强行重建图谱。
- `.understand-anything/knowledge-graph.json` 是分析产物，不是业务源码。除非用户明确要求更新/删除图谱，否则不要手动编辑或清空 `.understand-anything/`。
- 如果图谱不存在或明显过期，先运行 `/understand --language zh`；如果需要完整重扫，运行 `/understand --full --language zh`。
- 生成图谱后，优先用 `/understand-chat <问题>` 查询入口、调用链、依赖关系和影响面，再进入实现。

推荐提问：
- `/understand-chat 设备管理页面的数据从哪里来？`
- `/understand-chat 登录、权限、菜单和路由之间是什么关系？`
- `/understand-chat 修改聊天 SSE 流式输出会影响哪些模块？`
- `/understand-chat 知识库上传功能涉及哪些前端页面、API 模块和后端接口？`

给后续 AI 的约束：
- 使用 Understand Anything 得到的是辅助上下文，最终改动仍必须回到真实源码核验。
- 不要把图谱结论当成唯一事实；关键路径要用 `rg` / 文件读取 / 测试再次确认。
- 本项目运行、测试、依赖安装仍必须遵守 Docker-only 规则；Understand Anything 只用于代码理解，不替代 `docker compose ...` 验证。
- 根目录 `understand-anything-guide.html` 是给人看的快速说明页，可作为新协作者了解工具用途的入口。

## COMMANDS

```bash
# 一键起全栈（首次会构建镜像 + 自动迁移 + 创建 admin + 种子）
docker compose up -d

# 单独重建后端镜像（修了 requirements.txt / Dockerfile / settings 后必跑）
docker compose build backend && docker compose up -d backend celery_worker celery_beat

# 看后端日志（聊天室流式排障必备，关注 chat.send.* / chat.conversation.config_updated）
docker compose logs -f backend

# 进容器跑 manage.py / shell
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py test apps.resources.tests

# 进 web 容器装/升级前端依赖（禁止宿主 npm install）
docker compose exec web npm install <pkg>
docker compose exec web npm run lint

# 看前端 dev server 日志（HMR / 代理排障）
docker compose logs -f web
```

## NOTES

- 宿主端口刻意避开默认值（5432 → 5433、6379 → 6380、5173 → 5175、8000 → 8880），多项目并存不冲突；如果改回默认要同步 `web/.env` 的代理目标和后端 CORS 白名单。
- backend 容器启动序列固化在 compose `command:` inline shell：`migrate → seed_operations_periodic_tasks → collectstatic --noinput → 自动建 admin → seed_devices → uvicorn`。新增初始化步骤插这条链路里、不要另开 entrypoint 脚本。
- `web` 容器走 `npm run dev` + 挂载源码 + 匿名 `node_modules` 卷，**是开发态而非生产态**。生产部署需要另写一份 compose 或 Dockerfile 改成 `npm run build` + 静态托管。
- 国内镜像默认值：APT 走阿里云 Debian、PyPI 走清华 Tsinghua，由 `x-backend-build.args` 注入；离线 / 海外环境覆盖根 `.env` 即可。
- 子目录文档同时维护两份：`AGENTS.md`（quick-ref）+ `CLAUDE.md`（详细 FAQ + Changelog）。新增模块文档遵循同一对偶。
- 每次执行完任务之后都需要提交代码（非远端）使用中文去执行commit
- 如果需要测试openai兼容接口，请使用 groq 
    - 地址 https://api.groq.com/openai/v1
    - 密钥请从环境变量 `GROQ_API_KEY` 读取，禁止提交明文密钥
    - 模型名称 qwen/qwen3-32b
- 公司管理员和公司的员工权限是一样的 除了员工看不到公司管理员才能看到的员工管理 其他功能全部一模一样 后续这个问题不要再次询问。
- 安卓设备或者其他设备可以通过 X-Device-Code 去请求全部接口而不需要JWT
- 每一次需求的修改都需要考虑到异步的情况（结合现有docker-compose.yaml应用）

## 务必遵循

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
