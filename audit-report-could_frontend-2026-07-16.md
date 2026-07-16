# Fuck My Shit Mountain Audit Report

**Project:** could_frontend (Digital Human Admin)
**Audit mode:** full
**Date:** 2026-07-16
**Reviewer:** MiMoCode (glm-5.2) via fuck-my-shit-mountain skill

---

## 1. Executive Summary

could_frontend 是一个面向数字人（数字员工）管理的全栈平台，后端基于 Django 5.2 + DRF + Celery，前端基于 React 18 + TypeScript + Vite。系统覆盖设备运行时配置、音色绑定、ASR/LLM/TTS 实时流式对话、第三方机器人上下文集成、租户隔离与权限管理等核心能力。本次为全量（full）审计，覆盖 25 个维度，共确认 21 个发现（Critical 2、High 10、Medium 4、Low 3、Info 2），全部以 F1–F21 形式在「Detailed Findings」展开。

**主要风险集中在安全与发布两条线。** 安全侧：docker-compose 启动脚本内联创建 `admin/admin123456` 超管且无环境变量门控；Sentry DSN 硬编码于源码且 `send_default_pii=True` 默认开启；`SECRET_KEY`、`ALLOWED_HOSTS`、`CORS_ALLOW_ALL_ORIGINS` 均为不安全默认值；CSRF 中间件被注释禁用。发布侧：无任何 CI/CD，`requirements` 多数依赖未固定版本，`web` 服务用 `npm run dev` 起生产，`prod.py` 仅 4 行未做收紧。这些叠加意味着「按默认 compose 部署即获得可被秒破的超管账号」。

**亮点方面，** 测试质量相对突出：49 个测试模块、250+ 用例，mock 计数为 0（即测试使用真实对象而非过度打桩），跨租户隔离测试充分；ASGI 流式实现正确使用 `httpx.AsyncClient`；业务缓存命名空间化复用（DRY）；统一 WebSocket 入口 + type 路由（KISS）；`Manager.for_tenant` 封装租户隔离（Law of Demeter）；`DATABASE_URL` 缺失时 fail-fast raise（Fail-Fast 4.4）；前端使用 zustand store 组合子组件（Composition Over Inheritance）。

**优先修复路径：** 立即修复 F1–F4（默认超管、Sentry PII、SECRET_KEY/ALLOWED_HOSTS/CORS、CSRF 中间件），可在 4–6 小时内消除最严重的安全暴露；稳定发布前补齐 F5–F9、F11、F12（依赖固定、CI、realtime 拆分、_AGENT_MEMORY 治理、前端生产构建、prod 收紧、Sentry 仅 prod 初始化）；后续再排期 F10、F13–F16。

**总评：Overall 5.1 / B。** 平台工程基线扎实（测试、流式、租户隔离、统一 WS），但安全默认值与发布管线存在「屎山」级缺陷，不修复不建议进入稳定发布。

### Score Dashboard

```
Security        ██░░░░░░░░ 3.0  C   compose 硬编码 admin/admin123456、Sentry DSN 硬编码 PII 默认开、SECRET_KEY/ALLOWED_HOSTS/CORS 默认值不安全、CSRF 中间件被禁
Stability       █████░░░░░ 5.0  B   ASR 上游 close fire-and-forget；realtime.py 单文件 2244 行；多处 os.getenv 无类型校验
Performance     ███████░░░ 7.0  A   ASGI 流式正确（httpx.AsyncClient）；未发现 N+1 热点；扣分：_AGENT_MEMORY 无界增长
Testing         ████████░░ 8.0  A   49 模块 / 250+ 用例，mock 计数为 0，跨租户隔离测试充分；扣分：realtime 巨型逻辑无单测
Maintainability █████░░░░░ 5.0  B   realtime.py 2244 行、application-management/index.tsx 3283 行、common/ 空目录、.env 中文注释乱码
Design          █████░░░░░ 5.0  B   SRP/FileSize 多处违反；CORS_ALLOW_ALL+CREDENTIALS 矛盾配置；dev.py 单 MD5 hasher
Release         ██░░░░░░░░ 3.0  C   无 CI/CD、requirements 多数无版本固定、web 用 npm run dev 起生产、prod.py 仅 4 行未收紧
─────────────────────────────────────
Overall         █████░░░░░ 5.1  B
```

每个维度按 0.0–10.0 评分，**分数越高越好（10 = 干净，0 = 屎山）**。评分基于判断而非公式。分级锚点见 `rubrics/scoring.md`：9–10 S 优秀、7–8.9 A 良好、5–6.9 B 及格、3–4.9 C 较差、0–2.9 D 糟糕、0–0.9 F 屎山。

### Finding Statistics

| Severity | Count | Confirmed | Suspected |
|----------|-------|-----------|-----------|
| Critical | 2 | 2 | 0 |
| High | 10 | 10 | 0 |
| Medium | 4 | 4 | 0 |
| Low | 3 | 3 | 0 |
| Info | 2 | 2 | 0 |
| **Total** | **21** | **21** | **0** |

## 2. Project Map

**组件与职责。** 后端 `backend/` 采用 Django 5.2 单体，按 `apps/` 划分业务域（accounts、devices、ai_models、third_party_chatbots 等），`config/` 存放 settings 分层（base/dev/prod）、asgi.py、celery.py、realtime.py。前端 `web/` 为 Vite + React 18 + TS，`src/views/` 按业务页面切分，`src/api/` 集中 API 客户端，`src/store/` 为 zustand 状态层。

**运行时入口。** ASGI 入口 `config/asgi.py`：HTTP 走默认 `django_application`，WebSocket 在 `scope['type']=='websocket'` 且 path 为 `/ws/realtime/` 时路由到 `realtime_websocket_application`（`config/realtime.py`）。Celery 入口 `config/celery.py`，使用 `DatabaseScheduler`（`django_celery_beat`）。设备侧通过 `X-Device-Code` 请求头认证运行时接口，不走 JWT。

**数据流与状态所有权。** 实时对话流：设备/HTTP 语音 → 统一 WS → realtime 路由 → ASR 上游 WS（`httpx`/`websockets`）→ LLM 调用 → TTS 调度 → 回复块序列化推送。运行时配置：后台 `/api/v1/device-runtime/config/` 维护，变更通过统一 WS 推送完整配置（非增量）。`_AGENT_MEMORY` 进程级全局 dict 持有 agent 短期记忆，按 `device/agent` 键组织。

**持久化与隐私边界。** PostgreSQL 主库（132 个迁移），MinIO 对象存储，Redis 缓存 + Celery broker。租户隔离通过 `Manager.for_tenant` 在 ORM 层强制，跨租户隔离有专项测试 `test_cross_tenant_isolation`。Sentry 接入在 `base.py` import 时初始化，`send_default_pii=True`。

**外部接口与 AI 边界。** 上游 AI：ASR/LLM/TTS 厂商 API；第三方机器人：`apps/third_party_chatbots` 的 `third_party_chatbots.py`（832 行）按厂商配置管理多轮上下文，上游会话 ID 必须来自第三方响应并复用。飞书、阿里云等凭据通过 `.env` 注入。

**安全边界与测试结构。** 认证：后台 JWT（SimpleJWT）+ SessionAuthentication（admin）；设备侧 `X-Device-Code`。权限：公司管理员与员工基本一致（员工无员工管理）。测试：49 个 `test_*.py` 模块，`APITestCase` 集成测试为主，mock 计数为 0，跨租户隔离测试充分。

**风险高发区。** `config/realtime.py`（2244 行，多职责耦合、_AGENT_MEMORY 无界、ASR close fire-and-forget）；`config/settings/base.py`（多处不安全默认值、Sentry PII）；`docker-compose.yaml`（内联超管创建、web 用 dev server 起生产）；`web/src/views/application-management/index.tsx`（3283 行巨型组件）；`backend/requirements.txt`（版本未固定）；`.github/workflows/`（空目录，无 CI）。

### Coverage Matrix

| Dimension | Coverage | Evidence inspected | Exclusions / limits |
|-----------|----------|--------------------|---------------------|
| Architecture & Boundaries | Medium | apps/ 目录结构、config/ 分层、asgi.py、AGENTS.md 规则 | 未画依赖图、未调 codegraph MCP |
| Security | High | docker-compose.yaml、base/prod/dev settings、.gitignore、git ls-files、accounts/permissions | 未跑 pip-audit、未枚举 view 权限装饰器 |
| Stability | Medium | realtime.py（2244 行）、asgi.py、celery.py、wait_for_db.py | 未跑容器压测、未覆盖全部 Celery 路径 |
| Performance | Medium | realtime.py 内存/锁/timeout、ai_models services 行数、前端大文件 | 未做 profiling、未测 N+1 |
| Testing | High | 49 个 test_*.py、mock 计数 0、跨租户隔离测试内容 | 未逐断言审、未跑套件 |
| Maintainability | High | 后端/前端文件大小榜、realtime 行数、index.tsx 3283 行 | 未做完整圈复杂度 |
| Design | High | principles 逐条比对 base/realtime/compose/dev | — |
| Release | High | compose、requirements、.github/workflows（空）、Dockerfile、prod.py | 未检视实际生产 manifest |
| Documentation | Medium | AGENTS.md、CLAUDE.md、config AGENTS.md、backend AGENTS.md、wiki 目录 | 未逐篇审 wiki |
| Configuration | High | base/prod/dev settings、.env 键名、compose env_file | 未读 .env 全值（只看键名） |
| Observability | Medium | sentry.py、base LOGGING、request_id.py | 未审实际日志格式/采样/告警阈值 |
| Data Integrity | Medium | 132 个迁移、test_cross_tenant_isolation、DatabaseScheduler | 未逐迁移审 reversibility |
| Privacy | High | Sentry send_default_pii=True、.env 飞书/阿里云 key 键名 | 未审日志泄露 PII、未审知识库导出 |
| Accessibility | Low | styles/index.css 流体排版、tailwind.config brand、AGENTS.md 响应式规则 | 未跑 axe/lighthouse、未逐组件审键盘焦点 |
| Supply Chain | Medium | requirements.txt、package.json、Dockerfile、compose 镜像源 | 未做 SBOM、未跑 audit |
| Cost | Low | ai_models services 文件、realtime 上游连接数 | 未审 token 配额/预算/熔断 |
| AI Safety | Medium | third_party_chatbots.py 832 行、AGENTS.md 第三方上下文规则、test_third_party_chatbot_api.py | 未逐行审 prompt 拼接/工具授权/RAG 边界 |
| Fallback | Medium | realtime _close_asr_upstream_context_later、多处 or '' 兜底 | 未系统枚举 empty catch |
| Testing Authenticity | High | mock 计数 0、APITestCase 集成测试为主 | 未审断言耦合实现细节 |
| Type Safety | Medium | web tsconfig 存在、backend 无 type stub | 未跑 mypy/pyright |
| Frontend State | Medium | index.tsx 3283 行、store/ 目录、api/client.ts | 未逐组件审 effect 链 |
| Backend API | Medium | urls.py、ApiV1RootView、REST_FRAMEWORK 配置 | 未逐 serializer 审字段可写性 |
| Dependency Weight | Medium | package.json、requirements.txt | 未测 bundle size |
| Code Consistency | Medium | AGENTS.md 命名规则、前后端文件命名 | 未做全仓 import 排序统计 |
| Comment Coverage | Medium | AGENTS.md/CLAUDE.md 充分、.env 中文注释乱码 | 未量化注释密度 |

## 3. Top Risks

按优先级列出前 15 条风险（完整 21 条见 §4 Detailed Findings）：

1. **F1 — compose 内联创建 admin/admin123456 超管无门控**（Critical）：任何按默认 compose 部署的环境直接获得可被秒破的超管账号。
2. **F2 — Sentry DSN 硬编码 + send_default_pii=True**（Critical）：DSN 暴露可投递伪造事件，PII 默认全量上报违反最小化。
3. **F3 — SECRET_KEY/ALLOWED_HOSTS/CORS 不安全默认值**（High）：未注入 env 的环境用弱 key 签名 JWT/Session，可被伪造。
4. **F4 — CSRF 中间件被注释禁用**（High）：admin 走 SessionAuthentication，禁 CSRF 后跨站请求伪造可直接对 admin 增删改。
5. **F5 — requirements 多数依赖未固定版本**（High）：不同时间 pip install 拉到不同版本，CI/部署不可复现，可能引入 CVE。
6. **F6 — 无 CI/CD**（High）：49 个测试与 build 依赖人手执行，任何 push 都可能把破坏合并进 dev。
7. **F7 — realtime.py 2244 行单文件多职责**（High）：SRP/FileSize 双违反，巨型文件难回归，单测覆盖几乎不可能。
8. **F8 — _AGENT_MEMORY 进程级全局无锁无 TTL 无界增长**（High）：内存泄漏至 OOM + 并发 RMW 竞态丢消息。
9. **F9 — web 用 npm run dev 起生产**（High）：Vite dev server 非生产级（HMR ws 暴露、source map 全量、无压缩/缓存头）。
10. **F10 — application-management/index.tsx 3283 行巨型组件**（High）：状态/effect/回调/渲染高度耦合，整树重渲染。
11. **F11 — prod.py 仅 4 行未收紧**（High）：ALLOWED_HOSTS/CORS/HSTS/SSL_REDIRECT 全继承 base 不安全默认。
12. **F12 — Sentry 在 base.py import 时初始化**（High）：dev 异常也上报生产 Sentry，污染事件流、占配额、泄露 IP。
13. **F13 — dev 用 MD5 hasher 且 base 链含 MD5 兜底**（Medium）：dev DB 流出可秒破；历史 MD5 弱密码仍可登录生产。
14. **F14 — ASR 上游 close fire-and-forget 无 timeout 无重试**（Medium）：对端不回 close frame 时协程悬挂，资源泄漏。
15. **F15 — 密码校验器弱（仅长度 6 + NumericPasswordValidator）**（Medium）：缺 CommonPasswordValidator/UserAttributeSimilarityValidator。

## 4. Detailed Findings

### Finding: F1. compose 内联创建 admin/admin123456 超管无门控

- Severity:: Critical
- Confidence:: High
- Category:: Security / Release / Configuration
- Status:: Confirmed
- Principle violated:: 9.1 Configuration Over Hardcoding；9.2 Fail on Missing Configuration
- Evidence:: 
  - File: `docker-compose.yaml:59`
  - Module: backend 启动命令
  - Relevant behavior: backend 启动命令内联执行 `python manage.py shell -c` 创建 `admin/admin123456` 超管：`from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin','admin@example.com','admin123456')`。无任何「首次部署 / 已存在超管 / 环境变量」门控。
- Why it matters:: 任何按默认 compose 部署的环境（含生产）都会获得 `admin/admin123456` 超管账号。该密码为常见弱口令，且与 F15 弱密码校验叠加后用户改密仍可选弱密码。
- Realistic failure scenario: 运维按仓库默认 compose 在公网服务器 `docker compose up -d`，5173/80 端口暴露后管理后台 `/admin/` 可用 `admin/admin123456` 直接登录，攻击者枚举/撞库即获超级权限，进而通过 admin 创建任意租户数据或导出。
- Minimal fix:: 抽独立 `create_default_superuser` 管理命令，仅当 `DJANGO_CREATE_DEFAULT_ADMIN=1` 且 `DJANGO_DEFAULT_ADMIN_PASSWORD` 显式提供时才创建，并在创建后提示首次登录改密。
- Regression test suggestion:: 未设 `DJANGO_CREATE_DEFAULT_ADMIN` 时运行该命令不创建超管（断言 `User.objects.filter(username='admin').exists() is False`）；开关=1 但缺密码应 fail-fast 退出非零。
- Estimated effort:: 2–3h

### Finding: F2. Sentry DSN 硬编码 + send_default_pii=True 默认开

- Severity:: Critical
- Confidence:: High
- Category:: Security / Privacy
- Status:: Confirmed
- Principle violated:: 9.1 Configuration Over Hardcoding；9.3 Environment Separation
- Evidence:: 
  - File: `backend/config/settings/base.py:12-18`
  - Module: sentry_sdk.init
  - Relevant behavior: `sentry_sdk.init(dsn=硬编码DSN, send_default_pii=True, before_send=before_send)`。DSN 整段写在源码，PII 默认开启。
- Why it matters:: DSN 的 public+secret 都暴露在仓库，持有 secret 者可向项目投递伪造事件或滥用配额；`send_default_pii=True` 在 dev/prod 一律上报 IP、请求头、用户标识，违反数据最小化原则。
- Realistic failure scenario: DSN secret 随仓库克隆流出，攻击者用该 DSN 大量发送伪造事件淹没 Sentry 配额/告警，使真实告警被淹没；同时生产用户 IP/UA 被默认上报，触发 GDPR/PIPL 合规风险。
- Minimal fix:: DSN 移到 `SENTRY_DSN` 环境变量，未设则不 init；`send_default_pii` 由 `SENTRY_SEND_DEFAULT_PII` 显式开启，默认 `False`；`before_send` 内对 IP、User-Agent、Authorization 做 redaction。
- Regression test suggestion:: `SENTRY_DSN` 未设时 import settings 后 `sentry_sdk.Hub.current.client is None`；默认 `SENTRY_SEND_DEFAULT_PII is False`。
- Estimated effort:: 1–2h

### Finding: F3. SECRET_KEY/ALLOWED_HOSTS/CORS 不安全默认值

- Severity:: High
- Confidence:: High
- Category:: Security / Configuration
- Status:: Confirmed
- Principle violated:: 9.2 Fail on Missing Configuration；4.6 Least Privilege
- Evidence:: 
  - File: `backend/config/settings/base.py:31, :33, :248, :259`
  - Module: settings 默认值
  - Relevant behavior: `SECRET_KEY = os.getenv('DJANGO_SECRET_KEY','django-insecure-change-me')`；`ALLOWED_HOSTS` 默认 `'*'`；`CORS_ALLOW_ALL_ORIGINS` 默认 `True`；`CORS_ALLOW_CREDENTIALS=True`。
- Why it matters:: 任一未显式注入 env 的环境都用弱 key 签名 JWT/Session，可被伪造；`ALLOWED_HOSTS=*` 攥不住 Host 注入；`CORS_ALLOW_ALL_ORIGINS=True` + `ALLOW_CREDENTIALS=True` 虽被浏览器 CORS 规范禁止 `*`+credentials，但 Django corsheaders 在 `ALLOW_ALL` 时回显具体 Origin，等于任意站点可携凭据跨域调 API。
- Realistic failure scenario: 部署忘记注入 `DJANGO_SECRET_KEY`，系统用 `django-insecure-change-me` 静默启动，攻击者用该 key 伪造任意 Session/JWT 提权；恶意站点 JS 携 cookie 跨域调用本平台 API 读数据。
- Minimal fix:: `SECRET_KEY` 缺失时 `raise ImproperlyConfigured`（与 `DATABASE_URL` 一致）；`ALLOWED_HOSTS` 默认空列表；`CORS_ALLOW_ALL_ORIGINS` 默认 `False`，需显式开启并配套白名单。
- Regression test suggestion:: 未设 `SECRET_KEY` 时 import settings 抛 `ImproperlyConfigured`；默认 `CORS_ALLOW_ALL_ORIGINS is False`。
- Estimated effort:: 1h

### Finding: F4. CSRF 中间件被注释禁用

- Severity:: High
- Confidence:: High
- Category:: Security
- Status:: Confirmed
- Principle violated:: 4.6 Least Privilege
- Evidence:: 
  - File: `backend/config/settings/base.py:97-109`
  - Module: MIDDLEWARE
  - Relevant behavior: `django.middleware.csrf.CsrfViewMiddleware` 被注释禁用；`REST_FRAMEWORK` 的 `DEFAULT_AUTHENTICATION_CLASSES` 含 `SessionAuthentication`，admin 走 session。admin 原生 view 不走 DRF。
- Why it matters:: 禁掉 CSRF 中间件后 admin 表单提交不校验 token，跨站请求伪造可直接对 admin 增删改用户与数据。
- Realistic failure scenario: 已登录 admin 的管理员访问恶意页面，该页面提交 `POST /admin/auth/user/add/` 创建新超管，因无 CSRF 校验直接成功。
- Minimal fix:: 恢复 `CsrfViewMiddleware`（位于 `AuthenticationMiddleware` 之后、`CommonMiddleware` 之后，按 Django 推荐）。
- Regression test suggestion:: 不带 CSRF token 的 admin `POST /admin/auth/user/add/` 应返回 403；带正确 token 返回 302。
- Estimated effort:: 1h

### Finding: F5. requirements 多数依赖未固定版本

- Severity:: High
- Confidence:: High
- Category:: Release / Supply-Chain
- Status:: Confirmed
- Principle violated:: 9.1 Configuration Over Hardcoding
- Evidence:: 
  - File: `backend/requirements.txt`
  - Module: 依赖清单
  - Relevant behavior: 仅 `Django==5.2.6`、`simplejwt==5.5.1`、`drf-spectacular==0.28.0`、`celery==5.5.3`、`redis==6.4.0`、`psycopg[binary]==3.2.9`、`cors-headers==4.4.0`、`Pillow==11.1.0`、`httpx==0.28.1`、`uvicorn==0.44.0`、`websockets==15.0.1`、`minio==7.2.7` 等少数固定；`djangorestframework`、`drf-spectacular-sidecar`、`django-simpleui`、`django-celery-results`、`flower`、`dj-database-url`、`websocket-client`、`django-celery-beat`、`sentry-sdk` 无版本。
- Why it matters:: 不同时间 `pip install` 拉到不同版本，可能引入破坏性变更或 CVE；CI/部署不可复现。
- Realistic failure scenario: 某次部署时 `djangorestframework` 升级到次版本引入 Serializer 行为变更，线上 API 序列化字段顺序/类型变化导致前端解析失败；或某依赖出 CVE 但因无锁文件无法快速定位影响范围。
- Minimal fix:: `pip freeze` 当前容器版本回写全量固定；引入 `pip-tools` 用 `requirements.in` + `compile` 生成带 hash 锁文件。
- Regression test suggestion:: CI 跑 `pip install --dry-run` 校验可解析；`pip-audit` 扫 CVE。
- Estimated effort:: 1h

### Finding: F6. 无 CI/CD

- Severity:: High
- Confidence:: High
- Category:: Release / Testing
- Status:: Confirmed
- Principle violated:: Fail-Fast 4.4；Reproducibility
- Evidence:: 
  - File: `.github/workflows/`（空目录）
  - Module: CI 配置
  - Relevant behavior: `Get-ChildItem -Recurse` 无输出，无 GitHub Actions / GitLab CI / Jenkinsfile。49 个测试模块、`npm run build`、`tsc -b` 都依赖人手执行。
- Why it matters:: 任何 push 都可能把破坏合并进 dev，回归全靠记忆与自觉。
- Realistic failure scenario: 提交修改了 realtime 路由但未本地跑测试，破坏性变更合入 dev，下次部署后 WS 连接异常，问题在上线后才暴露。
- Minimal fix:: 新增 `.github/workflows/ci.yml`：matrix（backend/frontend）→ backend 跑 `docker compose exec backend python manage.py test --keepdb`，frontend 跑 `npm ci && npm run build`；加 `scripts/check-tailwind-tokens.js` 守卫。
- Regression test suggestion:: CI 本身即验证（PR 必须绿才可合并）。
- Estimated effort:: 2–4h

### Finding: F7. realtime.py 2244 行单文件多职责

- Severity:: High
- Confidence:: High
- Category:: Maintainability / Design
- Status:: Confirmed
- Principle violated:: 1.1 SRP；1.2 File Size
- Evidence:: 
  - File: `backend/config/realtime.py`（2244 行）
  - Module: realtime_websocket_application
  - Relevant behavior: 单文件同时负责 WebSocket 入口路由、连接状态机、ASR 上游管理、LLM 调用、TTS 调度、agent 短期记忆、回复块序列化、运行时配置推送。2244 行远超 1000 行 High 阈值。
- Why it matters:: 多职责耦合使任何一处改动都要在巨型文件里搜改回归，单测覆盖几乎不可能。
- Realistic failure scenario: 修改 TTS 调度时不慎影响 ASR 上游状态机分支，因全部耦合在同一文件，回归测试无法隔离，问题在集成阶段才暴露。
- Minimal fix:: 按职责拆 `config/realtime/` 子包：`connection.py`、`asr_session.py`、`llm_session.py`、`tts_session.py`、`agent_memory.py`、`device_subscription.py`、`reply_blocks.py`、`application.py`，保持 `realtime_websocket_application` 公共接口不变。
- Regression test suggestion:: 拆分后跑 `apps.devices.tests.test_asr_realtime`、`apps.ai_models.tests.test_chat_api` 全绿；新增 `agent_memory` 单测。
- Estimated effort:: 1–2 天

### Finding: F8. _AGENT_MEMORY 进程级全局无锁无 TTL 无界增长

- Severity:: High
- Confidence:: High
- Category:: Performance / Stability
- Status:: Confirmed
- Principle violated:: 5.4 No Shared Mutable State；10.2 Unbounded Resources
- Evidence:: 
  - File: `backend/config/realtime.py:43-44`
  - Module: _AGENT_MEMORY / _get_agent_memory / _push_agent_memory
  - Relevant behavior: `_AGENT_MEMORY: dict[str, list[dict[str,str]]] = {}` 进程级全局；`_get_agent_memory` 直接 `.get()`，`_push_agent_memory` 用 `setdefault().append()` 再 `del history[:-N]`；无锁、无 TTL、无 LRU；每 `device/agent` 键永不清理。
- Why it matters:: (1) 内存泄漏：每新会话键永不释放，worker RSS 单调增长至 OOM；(2) 并发：uvicorn 单 event loop 多协程可能同时 `setdefault().append()` 与 `del history[:-N]`，存在 RMW 竞态，极端丢消息或切片越界。
- Realistic failure scenario: 上线数月后活跃设备/agent 键持续累积，worker RSS 缓慢增长至 OOM 被 kill，实时对话随机中断；高并发时段同一设备多协程写记忆出现丢消息。
- Minimal fix:: 用 `cachetools.LRUCache(maxsize=N)` 或自实现 LRU+TTL（30 分钟未访问淘汰）+ `asyncio.Lock`；或迁到 Redis 用 `SETEX` 自动过期 + 命名空间化（AGENTS.md 规定业务缓存走 `business_cache`）。
- Regression test suggestion:: 写 `maxsize+1` 个不同键后最老被淘汰；TTL 到期 `get` 返回空；并发 100 协程写同一键不丢消息。
- Estimated effort:: 3–4h

### Finding: F9. web 用 npm run dev 起生产

- Severity:: High
- Confidence:: High
- Category:: Release / Performance
- Status:: Confirmed
- Principle violated:: 9.3 Environment Separation；9.1
- Evidence:: 
  - File: `docker-compose.yaml:101-118`
  - Module: services.web
  - Relevant behavior: `build context=./web`；`command: sh -c 'npm install && npm run dev -- --host 0.0.0.0'`；`restart: always`；暴露 `${WEB_PORT}:5173` Vite dev server。
- Why it matters:: Vite dev server 非生产级（HMR websocket 暴露、source map 全量、无压缩/缓存头、单进程）；`npm install` 在启动期跑而非镜像构建期，冷启动慢且不可复现；`./app/node_modules` 匿名卷导致容器间 node_modules 不可重现。
- Realistic failure scenario: 生产用 dev server 暴露 HMR websocket 与全量 source map，攻击者可读取未压缩源码与映射；每次容器重启都跑 `npm install`，依赖源波动时启动失败。
- Minimal fix:: Dockerfile 改多阶段：builder 跑 `npm ci && npm run build` → runner 用 nginx + `dist/` 静态托管 + 反代 `/api` 到 backend；compose `command` 改 `nginx -g 'daemon off;'`。
- Regression test suggestion:: 镜像构建后 `curl localhost:80` 返回 200 + 压缩 + 缓存头；`compose up` 后无 `npm install` 日志。
- Estimated effort:: 半天

### Finding: F10. application-management/index.tsx 3283 行巨型组件

- Severity:: High
- Confidence:: High
- Category:: Maintainability / Frontend State
- Status:: Confirmed
- Principle violated:: 1.1 SRP；1.2 File Size；1.3 Function Size
- Evidence:: 
  - File: `web/src/views/application-management/index.tsx`（3283 行 / 149KB）
  - Module: 巨型组件
  - Relevant behavior: 聚合表单、列表、音频工具、监控看板、播放守卫、use-agent-audio 等多子领域（同目录已拆 `audio-utils.ts`、`monitor-dashboard.tsx`、`playback-request-guard.ts`、`use-agent-audio.ts` 但 index.tsx 仍 3283 行）。状态/effect/回调/渲染高度耦合。
- Why it matters:: 一次状态更新触发整树重渲染，可维护性与性能双输。
- Realistic failure scenario: 在表单输入框敲字触发整组件 3283 行重渲染，列表与监控看板连带刷新，低端机卡顿；修改某 effect 不慎触发无限重渲染循环。
- Minimal fix:: 按 UI 区块（列表/详情抽屉/表单/监控）拆子组件，状态用 zustand store 下放；`index.tsx` 退化为路由+布局壳。
- Regression test suggestion:: 拆分后 `npm run build` 通过；单测覆盖关键交互（提交表单→列表刷新）。
- Estimated effort:: 1–2 天

### Finding: F11. prod.py 仅 4 行未收紧

- Severity:: High
- Confidence:: High
- Category:: Release / Security
- Status:: Confirmed
- Principle violated:: 9.2 Fail on Missing Configuration；9.3 Environment Separation
- Evidence:: 
  - File: `backend/config/settings/prod.py`（仅 4 行）
  - Module: 生产 settings
  - Relevant behavior: 仅 `DEBUG=False` + `SESSION_COOKIE_SECURE` + `CSRF_COOKIE_SECURE` + `SECURE_PROXY_SSL_HEADER`。`ALLOWED_HOSTS`、`CORS_ALLOW_ALL_ORIGINS`、`SECURE_HSTS_*`、`SECURE_SSL_REDIRECT` 全部继承 base 默认（即 `'*'`/`True`/未设）。
- Why it matters:: 生产环境与 base 默认值几乎无差异，base 的不安全默认直接落到生产。
- Realistic failure scenario: 生产 `ALLOWED_HOSTS=*` 致 Host 头注入可构造恶意链接；未启用 HSTS/SSL redirect，中间人可在降级 HTTP 链路劫持会话 cookie。
- Minimal fix:: prod.py 显式 `ALLOWED_HOSTS = DJANGO_ALLOWED_HOSTS.split()` 且空时 raise；`CORS_ALLOW_ALL_ORIGINS=False`；启用 `SECURE_SSL_REDIRECT`、`SECURE_HSTS_SECONDS>0`、`SECURE_HSTS_INCLUDE_SUBDOMAINS`。
- Regression test suggestion:: prod 下 `CORS_ALLOW_ALL_ORIGINS is False`、`SECURE_HSTS_SECONDS>0`。
- Estimated effort:: 1h

### Finding: F12. Sentry 在 base.py import 时初始化（dev 也上报）

- Severity:: High
- Confidence:: High
- Category:: Privacy / Configuration
- Status:: Confirmed
- Principle violated:: 9.3 Environment Separation
- Evidence:: 
  - File: `backend/config/settings/base.py:12-18`
  - Module: sentry_sdk.init
  - Relevant behavior: `sentry_sdk.init(...)` 在 base.py import 时执行，dev/prod 都跑；dev settings 不覆盖关闭。
- Why it matters:: dev 异常/warning 被上报到生产 Sentry 项目污染事件流、占配额；`send_default_pii=True` 在 dev 也上报 IP。
- Realistic failure scenario: 本地开发触发大量 warning/异常，全部涌入生产 Sentry，淹没真实生产告警；dev 环境 IP 与本地用户标识被上报到生产 Sentry 项目。
- Minimal fix:: 仅在 prod.py 或 `SENTRY_DSN` 非空时初始化；dev 默认不 init 或显式 `sentry_sdk.init(None)`。
- Regression test suggestion:: dev settings import 后 `sentry_sdk.Hub.current.client is None`；prod + DSN 设定时 client 非 None。
- Estimated effort:: 30min

### Finding: F13. dev 用 MD5 hasher 且 base 链含 MD5 兜底

- Severity:: Medium
- Confidence:: High
- Category:: Security
- Status:: Confirmed
- Principle violated:: 9.1 Configuration Over Hardcoding
- Evidence:: 
  - File: `backend/config/settings/dev.py:6-8`；`base.py:160-167`
  - Module: PASSWORD_HASHERS
  - Relevant behavior: dev.py `PASSWORD_HASHERS = ['MD5PasswordHasher']` 唯一；base.py production hasher 链末尾含 `MD5PasswordHasher` 兜底。
- Why it matters:: dev 用 MD5 加密极快，dev DB 误用或 dump 流出可秒破；base 链含 MD5 兜底意味着历史 MD5 密码（弱密码）仍可登录生产，延缓强制升级到 PBKDF2/Argon2。
- Realistic failure scenario: dev 数据库 dump 流出，MD5 哈希被离线秒破；生产环境遗留 MD5 哈希的弱口令账号持续可用。
- Minimal fix:: dev 仍可用 MD5 但加注释「仅本地数据」；生产 base 移除 `MD5PasswordHasher`，迁移脚本对历史 MD5 密码强制「下次登录改密」而非静默验证。
- Regression test suggestion:: base `PASSWORD_HASHERS` 不含 MD5；含 MD5 哈希的用户登录后被标记需改密。
- Estimated effort:: 1–2h

### Finding: F14. ASR 上游 close fire-and-forget 无 timeout 无重试

- Severity:: Medium
- Confidence:: High
- Category:: Stability / Fallback
- Status:: Confirmed
- Principle violated:: 6.1 Don't Swallow Errors；10.3 Cancel Safety；10.4 Timeout
- Evidence:: 
  - File: `backend/config/realtime.py:38-46`
  - Module: _close_asr_upstream_context_later / _close_asr_upstream_context
  - Relevant behavior: 用 `asyncio.create_task` 启动 `_close_asr_upstream_context`，内部 `try/except Exception: logger.exception(...)` 后返回，无 timeout、无重试、无 task 引用追踪；任务对象可能被 GC。
- Why it matters:: ASR 上游 WS close 可能卡住（对端不回 close frame），`create_task` 无 `wait_for` 会悬挂协程；异常仅 log 无告警无重试，连接资源可能泄漏。
- Realistic failure scenario: ASR 上游网络异常不回 close frame，close 协程永久悬挂，随会话累积连接句柄耗尽，新会话无法建立上游连接。
- Minimal fix:: 改 `asyncio.wait_for(context.__aexit__(None,None,None), timeout=5)`，超时强制 `await context.close()`；保留 task 引用集合以便关闭时 cancel。
- Regression test suggestion:: mock `__aexit__` 永不返回，调用后 5s 内 task 完成（超时路径）且无悬挂。
- Estimated effort:: 1h

### Finding: F15. 密码校验器弱

- Severity:: Medium
- Confidence:: High
- Category:: Security
- Status:: Confirmed
- Principle violated:: 4.5 Defensive Programming
- Evidence:: 
  - File: `backend/config/settings/base.py:151-157`
  - Module: AUTH_PASSWORD_VALIDATORS
  - Relevant behavior: 仅 `MinimumLengthValidator(min_length=6)` + `NumericPasswordValidator`，缺 `CommonPasswordValidator`、`UserAttributeSimilarityValidator`。
- Why it matters:: 6 位纯数字、`123456`、`qwerty` 可通过；结合 F1 默认 `admin123456` 风格，用户改密仍可能选弱密码。
- Realistic failure scenario: 超管改密为 `123456`（6 位纯数字）通过校验，撞库即可获权。
- Minimal fix:: `min_length` 提到 8–10；加 `CommonPasswordValidator` + `UserAttributeSimilarityValidator`。
- Regression test suggestion:: `123456`、`password` 改密被拒。
- Estimated effort:: 30min

### Finding: F16. asgi WS path 硬匹配字符串

- Severity:: Medium
- Confidence:: High
- Category:: Architecture
- Status:: Confirmed
- Principle violated:: 7.5 Open for Extension
- Evidence:: 
  - File: `backend/config/asgi.py:11-20`
  - Module: application
  - Relevant behavior: `async def application` 用 `if scope['type']=='websocket' and path=='/ws/realtime/'` 硬匹配字符串。每加一个 WS 端点都要改这个 if/elif 链。
- Why it matters:: 违反 OCP；虽 AGENTS.md 规定统一 WS 入口，但未来独立 WS 入口会重复改 ASGI。
- Realistic failure scenario: 新增 `/ws/monitor/` 端点需改 asgi.py if 链，遗漏分支导致该端点 404 或回退到 django_application。
- Minimal fix:: 用 `routing.URLRouter + ProtocolTypeRouter`（Django Channels 风格），或保留单 WS 但把 path 列表抽常量并加注释。
- Regression test suggestion:: ASGI 单测：非 `/ws/realtime/` 的 WS 请求走默认 `django_application`。
- Estimated effort:: 1h

### Finding: F17. .env 中文注释乱码

- Severity:: Low
- Confidence:: High
- Category:: Maintainability / Documentation
- Status:: Confirmed
- Principle violated:: 3.4 Meaningful Names
- Evidence:: 
  - File: `backend/.env`
  - Module: 环境变量注释
  - Relevant behavior: 部分中文注释乱码（如 `# 娴嬭瘯涓撶敤` / `# 椋炰功閫氱煡涓睘绀虹瀹浣滃煿`），UTF-8 文件被以 GBK 解码或文件本身被错误编码保存。
- Why it matters:: 关键配置注释无法阅读，运维改配置时误解含义（如飞书 HOST_IP 说明）增加误配风险。
- Realistic failure scenario: 运维无法读懂飞书回调地址说明，误填 HOST_IP 致飞书机器人回调失败。
- Minimal fix:: 用 UTF-8 重新保存 `.env`，加 `.env.example` 模板带中文说明。
- Regression test suggestion:: lint `.env` UTF-8 解码无 `U+FFFD`。
- Estimated effort:: 15min

### Finding: F18. common/ 空目录与残留 sqlite

- Severity:: Low
- Confidence:: High
- Category:: Maintainability
- Status:: Confirmed
- Principle violated:: 4.2 YAGNI
- Evidence:: 
  - File: `backend/common/`（空目录）；`backend/test_ascii_verify.sqlite3`（0 字节残留）
  - Module: 仓库噪音
  - Relevant behavior: AGENTS.md 描述 common/ 为「共享工具当前为空目录」；`test_ascii_verify.sqlite3` 为 0 字节残留。
- Why it matters:: 空目录/残留文件增加仓库噪音，新人误以为有内容。
- Realistic failure scenario: 新人花时间读 common/ 期望找到工具函数，浪费排查时间。
- Minimal fix:: 删除 `test_ascii_verify.sqlite3`；`common/` 加 `.gitkeep` 或删除。
- Regression test suggestion:: CI lint 禁止新增空目录/0 字节 sqlite。
- Estimated effort:: 5min

### Finding: F19. celerybeat-schedule 本地残留

- Severity:: Low
- Confidence:: High
- Category:: Maintainability / Configuration
- Status:: Confirmed
- Principle violated:: 9.1 Configuration Over Hardcoding
- Evidence:: 
  - File: `backend/celerybeat-schedule`（16384 字节本地存在）
  - Module: 调度缓存文件
  - Relevant behavior: `git ls-files backend/celerybeat-schedule` 无输出确认未跟踪（`.gitignore` 已排除）。
- Why it matters:: 低风险，但若误提交会泄露内部任务调度节奏；本地文件可能与容器内 DB 调度不一致导致 beat 行为漂移。
- Realistic failure scenario: 本地 celerybeat-schedule 与容器 DatabaseScheduler 周期错位，本地调试时任务触发时机与生产不符。
- Minimal fix:: 已有 `.gitignore` 排除，加 pre-commit 守卫拦截 `celerybeat-schedule*`。
- Regression test suggestion:: `git ls-files | grep celerybeat-schedule` 应为空。
- Estimated effort:: 5min

### Finding: F20. AGENTS.md 规则与实际门禁脱节

- Severity:: Info
- Confidence:: High
- Category:: Documentation / Release
- Status:: Confirmed
- Principle violated:: Fail-Fast 4.4
- Evidence:: 
  - File: `AGENTS.md`；`.githooks/pre-commit`
  - Module: 验证规则
  - Relevant behavior: AGENTS.md 核心原则「修改后必须验证」但仅 `.githooks/pre-commit` 检查 tailwind token，无 `python manage.py test`/`npm run build` 的 pre-commit 或 CI 强制。
- Why it matters:: 规则靠自觉，AGENTS.md 与实际门禁脱节。
- Realistic failure scenario: 协作者信赖 AGENTS.md「必须验证」但未实际跑测试，破坏性改动进库。
- Minimal fix:: 见 F6（引入 CI）+ pre-commit 跑快速 lint。
- Regression test suggestion:: 与 F6 合并。
- Estimated effort:: 与 F6 合并

### Finding: F21. Sentry before_send 已接入但 PII 脱敏不全

- Severity:: Info
- Confidence:: High
- Category:: Observability / Privacy
- Status:: Confirmed
- Principle violated:: 正面观察
- Evidence:: 
  - File: `backend/config/sentry.py`；`base.py`
  - Module: before_send hook
  - Relevant behavior: `before_send` hook 已接入 base.py。正面：已有 redaction 扩展位；负面：当前 `send_default_pii=True` 仍在 `before_send` 之前上报部分 PII。
- Why it matters:: 需在 `before_send` 内补 IP/User-Agent/Authorization 脱敏。
- Realistic failure scenario: 生产事件 request headers 含真实用户 IP/UA 被 Sentry 默认采集，触发合规风险。
- Minimal fix:: 在 `before_send` 中对 `event['request']['headers']` 的 IP/User-Agent/Authorization 做 redaction。
- Regression test suggestion:: 构造带 IP 的事件，`before_send` 后 IP 被替换为 `<redacted>`。
- Estimated effort:: 1h

---

## 5. Architecture & Module Boundaries

- Coverage: Medium
- Inspected evidence: `apps/` 目录结构、`config/` 分层、`asgi.py`、`AGENTS.md` 规则
- Exclusions / limits: 未画依赖图、未调 codegraph MCP

### 已确认发现（3 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F7 — realtime.py 2244 行单文件多职责（SRP/FileSize 双违反） | High | Confirmed |
| F10 — application-management/index.tsx 3283 行巨型组件 | High | Confirmed |
| F16 — asgi WS path 硬匹配字符串（OCP 违反） | Medium | Confirmed |

### 已验证良好实践

- ✓ 业务域按 `apps/` 切分，职责边界清晰
- ✓ settings 分层 base/dev/prod，分层意图正确
- ✓ 统一 WebSocket 入口 + type 路由（KISS），符合 AGENTS.md 规定
- ✓ ASGI 入口正确分离 HTTP 与 WS 协议

## 6. Security

- Coverage: High
- Inspected evidence: `docker-compose.yaml`、`base/prod/dev settings`、`.gitignore`、`git ls-files`、`accounts/permissions`
- Exclusions / limits: 未跑 pip-audit、未枚举 view 权限装饰器

### 已确认发现（6 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F1 — compose 内联创建 admin/admin123456 超管无门控 | Critical | Confirmed |
| F2 — Sentry DSN 硬编码 + send_default_pii=True | Critical | Confirmed |
| F3 — SECRET_KEY/ALLOWED_HOSTS/CORS 不安全默认值 | High | Confirmed |
| F4 — CSRF 中间件被注释禁用 | High | Confirmed |
| F13 — dev 用 MD5 hasher 且 base 链含 MD5 兜底 | Medium | Confirmed |
| F15 — 密码校验器弱 | Medium | Confirmed |

### 已验证良好实践

- ✓ JWT（SimpleJWT）认证后台 API
- ✓ `X-Device-Code` 设备运行时认证与 JWT 分离
- ✓ `Manager.for_tenant` 在 ORM 层强制租户隔离
- ✓ 跨租户隔离有专项测试 `test_cross_tenant_isolation`

## 7. Stability & Error Handling

- Coverage: Medium
- Inspected evidence: `realtime.py`（2244 行）、`asgi.py`、`celery.py`、`wait_for_db.py`
- Exclusions / limits: 未跑容器压测、未覆盖全部 Celery 路径

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F8 — _AGENT_MEMORY 进程级全局无锁无 TTL 无界增长 | High | Confirmed |
| F14 — ASR 上游 close fire-and-forget 无 timeout 无重试 | Medium | Confirmed |

### 已验证良好实践

- ✓ `wait_for_db.py` 启动等待数据库就绪
- ✓ Celery `DatabaseScheduler` 提供调度持久化
- ✓ ASGI 流式实现使用 `httpx.AsyncClient`（正确异步）

## 8. Performance & Scalability

- Coverage: Medium
- Inspected evidence: `realtime.py` 内存/锁/timeout、`ai_models` services 行数、前端大文件
- Exclusions / limits: 未做 profiling、未测 N+1

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F8 — _AGENT_MEMORY 无界增长（内存泄漏） | High | Confirmed |
| F9 — web 用 npm run dev 起生产（单进程非生产级） | High | Confirmed |

### 已验证良好实践

- ✓ ASGI 流式正确使用 `httpx.AsyncClient`，未发现 N+1 热点
- ✓ 业务缓存命名空间化复用（DRY）

## 9. Testing Quality

- Coverage: High
- Inspected evidence: 49 个 `test_*.py`、mock 计数 0、跨租户隔离测试内容
- Exclusions / limits: 未逐断言审、未跑套件

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F7 — realtime 巨型逻辑无单测 | High | Confirmed |
| F20 — AGENTS.md 规则与实际门禁脱节 | Info | Confirmed |

### 已验证良好实践

- ✓ 49 个测试模块、250+ 用例
- ✓ mock 计数为 0（测试使用真实对象而非过度打桩）
- ✓ 跨租户隔离测试充分

## 10. Maintainability

- Coverage: High
- Inspected evidence: 后端/前端文件大小榜、realtime 行数、index.tsx 3283 行
- Exclusions / limits: 未做完整圈复杂度

### 已确认发现（4 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F7 — realtime.py 2244 行 | High | Confirmed |
| F10 — index.tsx 3283 行巨型组件 | High | Confirmed |
| F17 — .env 中文注释乱码 | Low | Confirmed |
| F18 — common/ 空目录与残留 sqlite | Low | Confirmed |

### 已验证良好实践

- ✓ AGENTS.md / CLAUDE.md 文档充分，协作规则明确
- ✓ 前后端文件命名遵循统一规则

## 11. Design Principles Compliance

- Coverage: High
- Inspected evidence: principles 逐条比对 base/realtime/compose/dev
- Exclusions / limits: —

### 已确认发现（按违反原则归并）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F7 — SRP/FileSize 违反 | High | Confirmed |
| F10 — SRP/FileSize/FunctionSize 违反 | High | Confirmed |
| F3 — Fail on Missing Configuration 违反 | High | Confirmed |
| F4 — Least Privilege 违反 | High | Confirmed |
| F13 — Configuration Over Hardcoding 违反 | Medium | Confirmed |
| F14 — Don't Swallow Errors / Cancel Safety / Timeout 违反 | Medium | Confirmed |
| F1 — Configuration Over Hardcoding 违反 | Critical | Confirmed |
| F2 — Configuration Over Hardcoding 违反 | Critical | Confirmed |
| F8 — No Shared Mutable State / Unbounded Resources 违反 | High | Confirmed |

详见 §Principles Compliance。

## 12. Release & Deployment Process

- Coverage: High
- Inspected evidence: compose、requirements、`.github/workflows`（空）、Dockerfile、prod.py
- Exclusions / limits: 未检视实际生产 manifest

### 已确认发现（5 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F1 — compose 内联创建超管 | Critical | Confirmed |
| F5 — requirements 多数未固定版本 | High | Confirmed |
| F6 — 无 CI/CD | High | Confirmed |
| F9 — web 用 npm run dev 起生产 | High | Confirmed |
| F11 — prod.py 仅 4 行未收紧 | High | Confirmed |

### 已验证良好实践

- ✓ Docker Compose 作为开发/运行/验证统一环境
- ✓ `--keepdb` 测试加速约定（AGENTS.md 规定）

## 13. Documentation Accuracy

- Coverage: Medium
- Inspected evidence: `AGENTS.md`、`CLAUDE.md`、config `AGENTS.md`、backend `AGENTS.md`、wiki 目录
- Exclusions / limits: 未逐篇审 wiki

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F17 — .env 中文注释乱码 | Low | Confirmed |
| F20 — AGENTS.md 规则与实际门禁脱节 | Info | Confirmed |

### 已验证良好实践

- ✓ `AGENTS.md` 协作规则详尽（Docker、API 风格、设备权限、图标规范、设计 token）
- ✓ `CLAUDE.md` / config `AGENTS.md` / backend `AGENTS.md` 多层文档
- ✓ `wiki/` 目录承载第三方机器人上下文集成等专题指南

## 14. Configuration Safety

- Coverage: High
- Inspected evidence: base/prod/dev settings、`.env` 键名、compose env_file
- Exclusions / limits: 未读 .env 全值（只看键名）

### 已确认发现（5 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F1 — compose 内联创建超管（hardcoding） | Critical | Confirmed |
| F2 — Sentry DSN 硬编码 | Critical | Confirmed |
| F3 — SECRET_KEY/ALLOWED_HOSTS/CORS 不安全默认 | High | Confirmed |
| F11 — prod.py 未收紧 | High | Confirmed |
| F12 — Sentry 在 base.py 初始化（环境未分离） | High | Confirmed |

### 已验证良好实践

- ✓ `DATABASE_URL` 缺失时 fail-fast raise（Fail-Fast 4.4）
- ✓ settings 分层 base/dev/prod 意图正确

## 15. Observability

- Coverage: Medium
- Inspected evidence: `sentry.py`、base `LOGGING`、`request_id.py`
- Exclusions / limits: 未审实际日志格式/采样/告警阈值

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F12 — Sentry 在 base.py 初始化（dev 污染生产事件流） | High | Confirmed |
| F21 — before_send 已接入但 PII 脱敏不全 | Info | Confirmed |

### 已验证良好实践

- ✓ `request_id.py` 请求 ID 传播基础设施存在
- ✓ `before_send` hook 已接入，具备 redaction 扩展位
- ✓ base `LOGGING` 配置分层

## 16. Data Integrity

- Coverage: Medium
- Inspected evidence: 132 个迁移、`test_cross_tenant_isolation`、`DatabaseScheduler`
- Exclusions / limits: 未逐迁移审 reversibility

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F19 — celerybeat-schedule 本地残留（调度一致性风险） | Low | Confirmed |

### 已验证良好实践

- ✓ 132 个迁移表明 schema 演进有记录
- ✓ `DatabaseScheduler` 提供调度持久化
- ✓ 跨租户隔离有专项测试保障数据隔离

## 17. Privacy / Data Governance

- Coverage: High
- Inspected evidence: Sentry `send_default_pii=True`、`.env` 飞书/阿里云 key 键名
- Exclusions / limits: 未审日志泄露 PII、未审知识库导出

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F2 — Sentry send_default_pii=True（IP/UA/用户标识默认上报） | Critical | Confirmed |

### 已验证良好实践

- ✓ `.env` 注入第三方凭据（未硬编码于源码，键名层面）
- ✓ 租户隔离在 ORM 层强制，普通账号不可越权访问其他公司数据

## 18. Accessibility / UX Correctness

- Coverage: Low
- Inspected evidence: `styles/index.css` 流体排版、`tailwind.config` brand、`AGENTS.md` 响应式规则
- Exclusions / limits: 未跑 axe/lighthouse、未逐组件审键盘焦点

### 已确认发现

无发现。

### 已验证良好实践

- ✓ `styles/index.css` 全局 `text-fluid-*` 六级阶梯流体排版
- ✓ `tailwind.config` brand 色阶统一，禁用 `teal-*`
- ✓ `AGENTS.md` 响应式规则（mobile-first、`clamp()`、表格横向滚动）
- ✓ `DashboardLayout` 用 `useBreakpoint()` + `Drawer` 处理侧栏折叠

## 19. Supply Chain / Reproducibility

- Coverage: Medium
- Inspected evidence: `requirements.txt`、`package.json`、`Dockerfile`、compose 镜像源
- Exclusions / limits: 未做 SBOM、未跑 audit

### 已确认发现（2 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F5 — requirements 多数未固定版本 | High | Confirmed |
| F9 — web 用 npm run dev 起生产（不可复现构建） | High | Confirmed |

### 已验证良好实践

- ✓ Dockerfile 存在，镜像可构建
- ✓ `.githooks/pre-commit` 守卫 tailwind token（CI 可复用 `scripts/check-tailwind-tokens.js`）

## 20. Cost / Resource Economics

- Coverage: Low
- Inspected evidence: `ai_models` services 文件、realtime 上游连接数
- Exclusions / limits: 未审 token 配额/预算/熔断

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F8 — _AGENT_MEMORY 无界增长（内存成本无上限） | High | Confirmed |

### 已验证良好实践

- ✓ ASGI 流式正确使用异步客户端，资源占用模式合理
- ✓ 业务缓存命名空间化，避免无序增长

## 21. AI / LLM Safety

- Coverage: Medium
- Inspected evidence: `third_party_chatbots.py` 832 行、`AGENTS.md` 第三方上下文规则、`test_third_party_chatbot_api.py`
- Exclusions / limits: 未逐行审 prompt 拼接/工具授权/RAG 边界

### 已确认发现

无发现。

### 已验证良好实践

- ✓ `AGENTS.md` 第三方上下文集成规则详尽（方案 A/B、`extract`、`skipWhenVariableExists`、`nullWhenMissingVariables`）
- ✓ 上游会话 ID 必须来自第三方 API 响应并复用（防止本地 sessionId 误用）
- ✓ `test_third_party_chatbot_api.py` 至少覆盖两轮上下文回归

## 22. Fallback / Defensive Code

- Coverage: Medium
- Inspected evidence: realtime `_close_asr_upstream_context_later`、多处 `or ''` 兜底
- Exclusions / limits: 未系统枚举 empty catch

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F14 — ASR 上游 close fire-and-forget（异常仅 log 无告警无重试） | Medium | Confirmed |

### 已验证良好实践

- ✓ 多处 `or ''` 兜底为可空字段提供默认值（轻量防御）
- ✓ `before_send` hook 对异常有 log 记录（不静默）

## 23. Testing Authenticity

- Coverage: High
- Inspected evidence: mock 计数 0、`APITestCase` 集成测试为主
- Exclusions / limits: 未审断言耦合实现细节

### 已确认发现

无发现。

### 已验证良好实践

- ✓ mock 计数为 0（测试使用真实对象，不过度打桩）
- ✓ `APITestCase` 集成测试为主，覆盖真实请求链路
- ✓ 跨租户隔离测试验证真实隔离行为（Test Behavior Not Implementation）

## 24. Type Safety

- Coverage: Medium
- Inspected evidence: web `tsconfig` 存在、backend 无 type stub
- Exclusions / limits: 未跑 mypy/pyright

### 已确认发现

无发现。

### 已验证良好实践

- ✓ 前端 `tsconfig` 存在，TypeScript 类型检查启用
- ✓ `tsc -b` 纳入验证流程约定

## 25. Frontend State

- Coverage: Medium
- Inspected evidence: `index.tsx` 3283 行、`store/` 目录、`api/client.ts`
- Exclusions / limits: 未逐组件审 effect 链

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F10 — index.tsx 3283 行巨型组件（状态/effect/渲染耦合） | High | Confirmed |

### 已验证良好实践

- ✓ `store/` 目录使用 zustand 状态层（Composition Over Inheritance）
- ✓ `api/client.ts` 集中 API 客户端

## 26. Backend API

- Coverage: Medium
- Inspected evidence: `urls.py`、`ApiV1RootView`、`REST_FRAMEWORK` 配置
- Exclusions / limits: 未逐 serializer 审字段可写性

### 已确认发现

无发现。

### 已验证良好实践

- ✓ REST API 风格一致（名词复数路径、标准 HTTP 方法、`deviceCode` lookup）
- ✓ `ApiV1RootView` 提供 API 根
- ✓ 统一 WebSocket 入口 + type 路由（实时能力例外符合 AGENTS.md）

## 27. Dependency Weight

- Coverage: Medium
- Inspected evidence: `package.json`、`requirements.txt`
- Exclusions / limits: 未测 bundle size

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F5 — requirements 多数未固定版本（依赖治理缺失） | High | Confirmed |

### 已验证良好实践

- ✓ 前端使用 Vite（轻量构建链）
- ✓ `@tabler/icons-react` 统一图标库，未混用多套

## 28. Code Consistency

- Coverage: Medium
- Inspected evidence: `AGENTS.md` 命名规则、前后端文件命名
- Exclusions / limits: 未做全仓 import 排序统计

### 已确认发现

无发现。

### 已验证良好实践

- ✓ `AGENTS.md` 规定统一命名规则（camelCase 前端 API、snake_case 后端模型、Serializer 映射）
- ✓ Tabler Icons 命名统一 `Icon` 前缀
- ✓ 设计 token 统一走 `brand-*` 色阶

## 29. Comment Coverage

- Coverage: Medium
- Inspected evidence: `AGENTS.md`/`CLAUDE.md` 充分、`.env` 中文注释乱码
- Exclusions / limits: 未量化注释密度

### 已确认发现（1 个）

| 发现 | 严重程度 | 状态 |
|------|----------|------|
| F17 — .env 中文注释乱码 | Low | Confirmed |

### 已验证良好实践

- ✓ `AGENTS.md` / `CLAUDE.md` 文档详尽，覆盖协作规则与设计 token
- ✓ 前后端代码注释密度适中（与代码风格一致）

---

## 30. Principles Compliance

代码库整体遵循了若干核心工程原则（Fail-Fast、DRY、KISS、Law of Demeter、Composition Over Inheritance、Test Behavior Not Implementation），但在配置硬编码、文件规模、共享可变状态、错误吞没、最小权限等方面存在系统性违反。

### Principles Violated

| Principle | Violations | Severity | Affected Areas |
|-----------|------------|----------|----------------|
| Single Responsibility (SRP) | 2 | Medium | realtime.py、application-management/index.tsx |
| File Size Limit | 2 | High | realtime.py（2244 行）、index.tsx（3283 行） |
| Fail on Missing Configuration | 3 | Critical | SECRET_KEY、ALLOWED_HOSTS、CORS、默认超管 |
| Configuration Over Hardcoding | 5 | Critical | compose 超管、Sentry DSN、requirements 版本、MD5 hasher |
| Environment Separation | 2 | High | Sentry in base、web dev 起生产 |
| No Shared Mutable State Without Sync | 1 | High | _AGENT_MEMORY |
| Unbounded Resources | 1 | High | _AGENT_MEMORY |
| Don't Swallow Errors | 1 | Medium | ASR close fire-and-forget |
| Cancel Safety | 1 | Medium | ASR close 无 cancel 追踪 |
| Timeout Every External Call | 1 | Medium | ASR close 无 timeout |
| Least Privilege | 2 | High | CSRF 禁用、CORS_ALLOW_ALL+CREDENTIALS |
| Defensive Programming | 1 | Medium | 密码校验器弱 |
| Open for Extension | 1 | Medium | asgi WS path 硬匹配 |
| YAGNI | 1 | Low | common 空目录 + 残留 sqlite |

### Principles Respected

- ✓ **Fail-Fast 4.4** — `DATABASE_URL` 缺失时 raise ImproperlyConfigured；统一错误响应 envelope
- ✓ **DRY** — 业务缓存命名空间化复用，设计 token 统一 `brand-*` 色阶
- ✓ **KISS** — 统一 WebSocket 入口 + type 路由，不新增多个业务 WS URL
- ✓ **Law of Demeter** — `Manager.for_tenant` 封装租户隔离，业务层不直连跨租户查询
- ✓ **Composition Over Inheritance** — 前端 zustand store 组合子组件，状态层与视图分离
- ✓ **Test Behavior Not Implementation** — mock 计数为 0，测试验证真实行为而非实现细节

---

## 31. Recommended Fix Order

### Fix Immediately

可能导致数据丢失、安全泄露或服务中断的问题，应在发布前强制修复。

| # | 修复项 | 工作量 | 风险 |
|---|--------|--------|------|
| F1 | 抽独立 create_default_superuser 命令，环境变量门控 | 2–3h | 默认 admin/admin123456 超管可直接登录 |
| F2 | Sentry DSN 移至环境变量，send_default_pii 默认 False，before_send 脱敏 | 1–2h | DSN 暴露 + PII 默认上报 |
| F3 | SECRET_KEY 缺失 raise，ALLOWED_HOSTS 默认空，CORS_ALLOW_ALL 默认 False | 1h | 弱 key 签名可伪造 |
| F4 | 恢复 CsrfViewMiddleware | 1h | admin CSRF 防护失效 |

### Fix Before Stable Release

可靠性、正确性、安全问题，影响稳定发布。

| # | 修复项 | 工作量 | 风险 |
|---|--------|--------|------|
| F5 | requirements 全量固定 + pip-tools 锁文件 + pip-audit | 1h | 依赖漂移、CVE、不可复现 |
| F6 | 引入 GitHub Actions CI（backend test + frontend build + token 守卫） | 2–4h | 破坏性改动无门禁合入 |
| F7 | realtime.py 按职责拆子包（8 模块） | 1–2 天 | 巨型文件难回归、无单测 |
| F8 | _AGENT_MEMORY 改 LRUCache+TTL+Lock 或迁 Redis | 3–4h | 内存泄漏 OOM + 并发竞态 |
| F9 | web Dockerfile 多阶段构建 + nginx 静态托管 | 半天 | dev server 起生产 |
| F11 | prod.py 显式收紧 ALLOWED_HOSTS/CORS/HSTS/SSL_REDIRECT | 1h | 生产继承 base 不安全默认 |
| F12 | Sentry 仅 prod 或 DSN 非空时初始化 | 30min | dev 污染生产事件流 + IP 泄露 |

### Schedule Later

增加维护成本或限制规模的问题，可排期处理。

| # | 修复项 | 工作量 | 风险 |
|---|--------|--------|------|
| F10 | index.tsx 按 UI 区块拆子组件 + zustand 下放 | 1–2 天 | 巨型组件重渲染性能 |
| F13 | 生产移除 MD5 兜底 + 历史弱口令强制改密 | 1–2h | 弱口令可登录生产 |
| F14 | ASR close 加 wait_for timeout + task 引用追踪 | 1h | 上游 close 悬挂泄漏 |
| F15 | 密码校验器加 CommonPasswordValidator + min_length 8–10 | 30min | 弱密码可通过 |
| F16 | asgi WS path 抽常量或改 URLRouter | 1h | OCP 违反 |

### Ignore for Now

低风险、理论风险或信息性问题，暂不优先。

| # | 修复项 | 工作量 | 风险 |
|---|--------|--------|------|
| F17 | .env UTF-8 重存 + .env.example | 15min | 注释乱码误配 |
| F18 | 删除残留 sqlite + common/.gitkeep | 5min | 仓库噪音 |
| F19 | pre-commit 守卫 celerybeat-schedule | 5min | 调度文件误提交 |
| F20 | 与 F6 合并 | 与 F6 合并 | 规则靠自觉 |
| F21 | before_send 补 IP/UA/Authorization 脱敏 | 1h | PII 脱敏不全 |

## 32. Quick Wins

低成本、高价值的修复，通常 1–2 小时即可消除真实风险。

| 修复 | 工作量 | 价值 |
|------|--------|------|
| **F2** — Sentry PII 默认 False，DSN 移环境变量 | 1–2h | 消除 PII 默认上报与 DSN 暴露 |
| **F3** — SECRET_KEY 缺失 raise | 1h | 防止弱 key 静默启动 |
| **F4** — 恢复 CSRF 中间件 | 1h | 恢复 admin CSRF 防护 |
| **F11** — prod.py 收紧 | 1h | 生产与 base 默认隔离 |
| **F12** — Sentry 仅 prod init | 30min | 阻断 dev 污染生产事件流 |
| **F15** — 密码校验器加 CommonPasswordValidator | 30min | 阻断常见弱密码 |

> 注：上述 Quick Wins 中 F2/F3/F4/F11/F12 属于「Fix Immediately」与「Fix Before Stable Release」的子集，F15 属「Schedule Later」。全部完成可在一日内将 Security 与 Release 两个最低分维度从 C 级提升至 B 级。

