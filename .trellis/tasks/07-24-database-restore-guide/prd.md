# 数据库备份恢复排障与操作手册

## Goal

诊断从本机 PostgreSQL 数据库导出的 Navicat 结构与数据 SQL 在克隆项目的 Linux 虚拟机中恢复失败的根因，并交付一份可以实际照做的中文网页手册，让用户能以 Navicat 为主或纯命令行两种方式完成数据库迁移、验证和失败回滚。

## Background

- 源项目/数据库位于 `192.168.3.90`，源库名由导出文件确认是 `digital_human`，PostgreSQL 版本是 16.14。
- 目标项目位于 Linux 虚拟机 `/home/cancer/workspace/could_frontend`，服务器地址是 `192.168.182.129`。
- 项目数据库服务使用 `pgvector/pgvector:pg16`，宿主机数据库端口由根目录 `.env` 的 `DB_PORT` 控制；当前仓库值为 `5433`。
- 两个 Navicat 导出文件均约 149.5 MB，但 SHA-256 不同，不应视为可互换的同一文件。
- 现有导出文件不是可靠的可移植恢复脚本：它直接导出 `vector` / `halfvec` / `sparsevec` 类型及 `$libdir/vector` 扩展内部函数，没有 `CREATE EXTENSION vector`；包含 90 个无 `CASCADE` 的 `DROP TABLE IF EXISTS`，且父表 `resources_scrollingtext` 早于依赖它的子表删除；没有 `BEGIN` / `COMMIT` 原子事务。
- 文件中 `(tenant_id, permissionpoint_id)=(1,80)` 只有一条 INSERT，重复键来自目标库在导入前或失败重跑后已存在的数据，而不是备份文件内自重复。
- Compose 的 `backend` 启动命令会先执行 Django migrations；`tenants/0002_default_company.py` 会向默认公司的权限关系表写入数据。恢复期间若未停止后台写服务，会污染目标库。
- `cannot change ownership of identity sequence` 来自 Navicat 对 identity sequence 额外执行 `ALTER SEQUENCE ... OWNED BY`，不是业务模型缺陷。

## Requirements

- R1：网页必须先解释每类错误的根因、严重性和是否可忽略，不能只堆命令。
- R2：提供 Navicat 优先方案，包含连接目标 PostgreSQL（直接连接和 SSH 隧道）、停止写服务、重建空库、正确备份/恢复、恢复后启动项目与验证的逐步操作。
- R3：提供命令行推荐方案，使用容器内 PostgreSQL 16 工具生成标准 `pg_dump` 备份并通过 `pg_restore` 或 `psql -v ON_ERROR_STOP=1` 恢复。
- R4：明确现有 Navicat `.sql` 不应继续原样重放；说明为何“删库、建扩展后再导入”仍然失败。
- R5：提供恢复前检查、恢复成功验证、常见错误处理、回滚/重做、媒体文件与 `.env` 迁移提醒。
- R6：所有会覆盖目标数据库的步骤必须带醒目的风险提示和前置确认清单；不自动连接或修改用户的虚拟机数据库。
- R7：网页不得写入明文 SSH 密码、数据库密码、Token 或其他凭据；用占位符提示用户输入。
- R8：页面使用简体中文，桌面与手机均可阅读，代码块可复制，Navicat 与命令行方案可清晰切换或跳转，并具备可访问的语义结构和焦点状态。
- R9：保持业务代码 diff 最小，不为数据库恢复问题修改 Django 模型、迁移或 Compose 启动逻辑。
- R10：最终交付为仓库根目录的单文件 `database-restore-guide.html`，不接入 React 路由，不依赖网络字体、CDN、构建工具或后端服务，双击即可打开。

## Acceptance Criteria

- [ ] AC1：网页逐项解释 `cannot drop table ... depends on it`、唯一键重复、identity sequence ownership、pgvector 内部函数/类型四类现有错误。
- [ ] AC2：Navicat 方案从连接参数来源开始，覆盖停止服务、空库确认、备份格式选择、恢复、验证和重启。
- [ ] AC3：命令行方案提供源端导出、文件传输、目标端恢复与验证的可复制命令，并避免在命令历史中硬编码密码。
- [ ] AC4：手册明确数据库恢复期间 `backend`、`celery_worker`、`celery_beat` 必须停止，恢复完成后再启动。
- [ ] AC5：手册包含至少一条确认库为空的 SQL，以及表数量、迁移状态、pgvector 扩展、关键数据数量和项目健康状态验证。
- [ ] AC6：页面不包含用户提供的明文密码；仓库敏感信息扫描不新增命中。
- [ ] AC7：页面在 375px 与桌面宽度无非预期横向滚动，交互无需依赖 hover，支持 `prefers-reduced-motion`。
- [ ] AC8：根据最终交付形态，通过对应 HTML 校验或项目 `npm run build`，并检查页面中的命令、路径和端口与仓库配置一致。
- [ ] AC9：根目录 `database-restore-guide.html` 在禁网环境仍能完整显示和执行复制/导航交互。

## Out Of Scope

- 自动登录、远程操作或覆盖 `192.168.182.129` 上的数据库。
- 修改历史 Django migrations 来适配错误的 Navicat 脚本。
- 把 PostgreSQL 数据库备份当作媒体文件、MinIO 数据或 `.env` 的替代品。
- 承诺不同 Navicat 大版本中完全一致的菜单文字；页面会同时给出稳定概念和常见中文菜单名。
