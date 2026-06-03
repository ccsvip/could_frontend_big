# Solin 容器依赖与启动流程

> 来源：[`docker-compose.yaml`](../docker-compose.yaml)
> 基线：6 个服务 — `db` / `redis` / `backend` / `celery_worker` / `celery_beat` / `web`
> 全部 `restart: always`；backend 三件套（backend / celery_worker / celery_beat）共用 `x-backend-build` 锚点

---

## 1. 依赖图（depends_on + condition）

```mermaid
flowchart LR
    classDef infra fill:#cfe8ff,stroke:#1e6091,color:#000
    classDef app fill:#d4edda,stroke:#1e6f3b,color:#000
    classDef worker fill:#fff3cd,stroke:#856404,color:#000
    classDef frontend fill:#f8d7da,stroke:#721c24,color:#000

    db[("solin_db<br/>postgres:16-alpine<br/>5432")]:::infra
    redis[("solin_redis<br/>redis:7-alpine<br/>6379")]:::infra
    backend["solin_backend<br/>uvicorn :8000<br/>healthcheck: TCP 8000"]:::app
    worker["solin_celery_worker<br/>celery -A config worker"]:::worker
    beat["solin_celery_beat<br/>celery -A config beat<br/>(DatabaseScheduler)"]:::worker
    web["solin_web<br/>vite dev :5173"]:::frontend

    db -- service_started --> backend
    redis -- service_started --> backend

    backend -. service_healthy .-> worker
    backend -. service_healthy .-> beat
    backend -. service_healthy .-> web

    db -- service_started --> worker
    redis -- service_started --> worker
    db -- service_started --> beat
    redis -- service_started --> beat
```

**约定**：
- 实线 `service_started` = 容器启动即放行（不等 healthcheck）
- 虚线 `service_healthy` = 必须 backend healthcheck 通过才放行
- worker / beat 同时挂 backend healthy + db/redis started，是双保险

---

## 2. 启动波次（按时间轴）

```mermaid
flowchart TB
    classDef wave fill:#e9ecef,stroke:#495057,color:#000,font-weight:bold
    classDef infra fill:#cfe8ff,stroke:#1e6091,color:#000
    classDef app fill:#d4edda,stroke:#1e6f3b,color:#000
    classDef worker fill:#fff3cd,stroke:#856404,color:#000
    classDef frontend fill:#f8d7da,stroke:#721c24,color:#000

    wave0[Wave 0 - 基础设施 并行无依赖]:::wave
    db[(db)]:::infra
    redis[(redis)]:::infra

    wave1[Wave 1 - backend owns schema]:::wave
    backend["backend<br/>6 步 inline shell<br/>详见 §3"]:::app

    wave2[Wave 2 - 消费方 等 backend healthy]:::wave
    worker["celery_worker<br/>migrate --check 后启 worker"]:::worker
    beat["celery_beat<br/>migrate --check 后启 beat"]:::worker
    web["web<br/>npm install 后启 vite dev"]:::frontend

    wave0 -.- db
    wave0 -.- redis
    db ==> wave1
    redis ==> wave1
    wave1 -.- backend
    backend ==> wave2
    wave2 -.- worker
    wave2 -.- beat
    wave2 -.- web
```

**关键约束**：
| 节点 | 等什么 | 为什么 |
|---|---|---|
| backend | db + redis `started` | 网络可达即可，不需要等 db ready |
| celery_worker / celery_beat | backend `healthy`（+ migrate --check 双保险） | 必须 schema 已迁移，否则 migrate 检查失败 → 容器重启循环 |
| web | backend `healthy` | Vite 启动后立刻代理 API，没起来会 502 |

**healthcheck 窗口**：TCP 8000 探测，`start_period=20s` + `interval=5s` × `retries=30` ≈ **170s 上限**。首次启动迁移多时可能超窗，需要调大。

---

## 3. backend 容器 inline shell 启动序列（Wave 1 内部）

> 来源：[`docker-compose.yaml`](../docker-compose.yaml#L45) `backend.command:`
> **6 步串行**，任何一步失败整个容器重启

```mermaid
flowchart TB
    s1["1. migrate<br/>应用所有 Django migrations<br/>(含 django_celery_beat / django_celery_results)"]
    s2["2. seed_operations_periodic_tasks<br/>注册周期任务<br/>(清理 7 天前 Celery 结果)"]
    s3["3. collectstatic --noinput<br/>收集静态资源到 staticfiles/<br/>(SimpleUI vendor 1500+ 文件)"]
    s4["4. 自动建 superuser<br/>admin / admin123456<br/>(已存在则跳过)"]
    s5["5. seed_devices<br/>设备种子数据"]
    s6["6. uvicorn config.asgi:application<br/>--host 0.0.0.0 --port 8000<br/>聊天室 SSE 真流式所必需"]

    s1 --> s2 --> s3 --> s4 --> s5 --> s6

    s6 -. 进入监听后 healthcheck 才会变 healthy .-> hc((healthcheck<br/>TCP 8000))
```

**坑点**：
- **不要**把 `uvicorn config.asgi` 换成 `wsgi`：聊天室 SSE 流式会立即退化成阻塞返回（详 [`backend/CLAUDE.md`](../backend/CLAUDE.md)）
- **不要**丢任何 seed 步骤：缺 `seed_devices` 设备列表空、缺 `seed_operations_periodic_tasks` 周期任务空、缺 superuser inline shell 卡 `/admin/` 入口
- 6 步固化在 compose `command:` 里，新增初始化插这条链路里、**不要**另开 entrypoint 脚本

---

## 4. 运行时数据流

```mermaid
flowchart LR
    classDef host fill:#fff,stroke:#000,stroke-dasharray: 3 3,color:#000
    classDef infra fill:#cfe8ff,stroke:#1e6091,color:#000
    classDef app fill:#d4edda,stroke:#1e6f3b,color:#000
    classDef worker fill:#fff3cd,stroke:#856404,color:#000
    classDef frontend fill:#f8d7da,stroke:#721c24,color:#000

    user(("👤 浏览器"))
    user -- ":5175 (host)" --> web

    web["web<br/>vite :5173"]:::frontend
    web -- "代理 /api → backend:8000" --> backend

    backend["backend<br/>uvicorn :8000"]:::app
    backend -- "ORM" --> db
    backend -- "cache + business_cache" --> redis
    backend -- "task.delay() → broker" --> redis

    redis[("redis :6379<br/>broker (DB 1) + cache (DB 0)")]:::infra
    db[("db :5432<br/>postgres")]:::infra

    worker["celery_worker"]:::worker
    worker -- "consume tasks" --> redis
    worker -- "ORM (notify_*)" --> db
    worker -- "result_backend=django-db" --> db

    beat["celery_beat"]:::worker
    beat -- "DatabaseScheduler 读 PeriodicTask 表" --> db
    beat -- "produce scheduled tasks → broker" --> redis

    host_db["host: localhost:5433<br/>(只读 GUI 客户端)"]:::host
    host_redis["host: localhost:6380<br/>(只读 GUI 客户端)"]:::host
    host_api["host: localhost:8880<br/>(curl / postman)"]:::host

    db -. 端口映射 .- host_db
    redis -. 端口映射 .- host_redis
    backend -. 端口映射 .- host_api
```

**容器内主机名**（**不**用 localhost）：
- backend / worker / beat → `db:5432` 连数据库
- backend / worker / beat → `redis:6379` 连缓存与 broker
- web → `backend:8000` 代理 API

**Redis 多用途**：
- DB 0：Django cache backend（`django.core.cache.backends.redis.RedisCache`）
- DB 1（默认）：Celery broker（`CELERY_BROKER_URL=redis://...:6379/1`）
- `business_cache.py` 走 cache backend，结果带 `business-cache:<namespace>:` 前缀做命名空间隔离

**Celery 任务谱**（实际 5 个 `@shared_task`）：
- `notify_account_application` — 账号申请飞书通知
- `notify_command_event_task` — 控制指令操作飞书通知
- `notify_command_change_task` — 控制指令名称变更飞书卡片
- `cleanup_old_celery_results` — 周期任务，每天 03:00 清 7 天前结果（已通过 `seed_operations_periodic_tasks` 注册）
- `config.celery.debug_task` — scaffolding 遗留，未使用

---

## 5. 操作命令速查

```bash
# 一次起全部（按依赖图自动按 3 波次起）
docker compose up -d

# 看实时状态（重点关注 backend 列的 healthy / starting / unhealthy）
docker compose ps

# 重建 backend 镜像后，三个共用镜像的容器一起拉起来对齐
docker compose build backend
docker compose up -d backend celery_worker celery_beat

# 看 backend 启动序列日志（排查 6 步哪步卡了）
docker compose logs -f backend

# 看 worker/beat 任务消费日志
docker compose logs -f celery_worker celery_beat

# 进容器跑 manage.py（docker-only 强约束，宿主禁止）
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py test apps.resources.tests
```

---

## 6. 故障定位决策树

```mermaid
flowchart TD
    start{"docker compose ps<br/>看到什么？"}

    start -- "backend = unhealthy" --> b1{"docker compose logs backend<br/>停在哪步？"}
    b1 -- "migrate 卡住" --> b1a["db 未起 → 检查 db 容器<br/>或 DATABASE_URL 写错"]
    b1 -- "collectstatic 报错" --> b1b["静态目录权限 / 磁盘空间"]
    b1 -- "uvicorn 起不来" --> b1c["端口冲突 / asgi.py 语法错"]
    b1 -- "20s 内没监听" --> b1d["调大 healthcheck.start_period"]

    start -- "worker / beat 不停重启" --> w1{"docker compose logs celery_worker<br/>停在哪？"}
    w1 -- "migrate --check 失败" --> w1a["backend 还没 migrate 完<br/>或 backend 没 healthy<br/>→ depends_on 配置错"]
    w1 -- "broker 连不上" --> w1b["redis 容器未起<br/>或 CELERY_BROKER_URL 写成 localhost"]

    start -- "web 502 / 起不来" --> wb1{"backend 是否 healthy?"}
    wb1 -- "否" --> wb1a["先修 backend"]
    wb1 -- "是" --> wb1b["VITE_API_PROXY_TARGET<br/>必须写 backend:8000<br/>不是 localhost"]

    start -- "全部 Up 但功能异常" --> f1{"是哪类功能?"}
    f1 -- "聊天室不流式" --> f1a["asgi 被换成 wsgi<br/>或同步 generator 包了 StreamingHttpResponse"]
    f1 -- "周期任务没跑" --> f1b["beat 容器未起<br/>或 PeriodicTask 未注册<br/>→ 重跑 seed_operations_periodic_tasks"]
    f1 -- "飞书通知不到" --> f1c["worker 容器未起<br/>或 FEISHU_WEBHOOK_URL 没配"]
```

---

## 关联文档

- [根 AGENTS.md](../AGENTS.md) — monorepo 编排约定 + ENVIRONMENT MANDATE
- [backend/AGENTS.md](../backend/AGENTS.md) — Django 模块约定
- [backend/config/AGENTS.md](../backend/config/AGENTS.md) — settings / urls / business_cache 细节
- [docker-compose.yaml](../docker-compose.yaml) — 真相源
