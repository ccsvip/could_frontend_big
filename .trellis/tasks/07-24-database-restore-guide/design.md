# 数据库恢复操作手册设计

## Scope And Boundary

交付物是仓库根目录单文件 `database-restore-guide.html`。它是离线运维文档，不进入 Vite/React 构建、不调用项目 API、不读取本地文件、不连接数据库。项目业务代码、Django migrations、Compose 配置保持不变。

## Information Architecture

1. 顶部结论区：直接说明现有 Navicat SQL 不能继续原样导入，以及唯一推荐原则“停写服务、空库、标准备份、遇错即停”。
2. 环境事实区：源/目标主机、项目路径、数据库名、端口来源、PostgreSQL/pgvector 版本关系；凭据只展示变量名或占位符。
3. 根因区：用错误原文、文件证据、因果链、处理结论逐项解释四类错误。
4. 恢复前总闸：备份目标库、停止三类写服务、确认连接、确认空库、记录媒体与 `.env` 边界。
5. 方案 A（Navicat 优先）：建立直接连接或 SSH 隧道、使用 Navicat Backup/Restore 重新生成可恢复备份、重建目标库、恢复、校验、启动服务。
6. 方案 B（命令行推荐）：容器内 `pg_dump -Fc`、`docker cp`、`scp`、目标端 `dropdb/createdb/pg_restore --exit-on-error`、校验与启动。
7. 验证矩阵：扩展、表、Django migrations、关键关系、序列、容器健康、登录与资源文件。
8. 故障处理：按错误文本给出立即停止、清理和重做路径；禁止在半恢复数据库上继续补丁式重跑。

## Interaction And Visual System

- 采用内容优先的技术文档布局：桌面端左侧锚点目录、右侧正文；窄屏改为顶部横向目录，不产生页面级横向滚动。
- 使用 CSS 自定义属性表达背景、正文、边框、主色、警告、危险、成功等语义色；不使用单一蓝紫或深色大面积主题。
- 字体使用系统中文无衬线栈，代码使用系统等宽字体，避免网络依赖和字体闪烁。
- 所有字号使用 `clamp()`；正文行高不低于 1.65，正文阅读宽度受控。
- 命令块允许自身横向滚动，页面容器不横向溢出；复制按钮使用文字标签并提供 `aria-live` 反馈。
- 锚点链接、复制按钮、方案入口均具有 `:focus-visible`；交互目标最小高度 44px。
- 仅使用轻量的颜色/阴影过渡，`prefers-reduced-motion` 下禁用平滑滚动和过渡。
- 不使用外部图片、字体、脚本或图标库；用纯 CSS 的流程轨道和状态标记承载必要视觉关系。

## Operational Contracts

### Navicat Contract

- Linux SSH 登录凭据与 PostgreSQL 数据库凭据明确分开。
- 数据库账号、库名和端口必须从目标项目 `.env` / `backend/.env` 获取，不把 SSH 用户当数据库用户。
- 恢复期间必须停止 `backend`、`celery_worker`、`celery_beat`。
- 优先使用 Navicat 的 PostgreSQL Backup/Restore 能力重新备份，而不是继续使用当前“转储 SQL（结构和数据）”文件。
- 若 Navicat 版本无法跨连接恢复备份，则回退到方案 B，不指导用户手工删除 149 MB SQL 中的扩展函数。

### Command-Line Contract

- 源端和目标端均从各自容器环境读取 `POSTGRES_USER` / `POSTGRES_DB`，命令不硬编码数据库密码。
- 标准备份采用 `pg_dump -Fc --no-owner --no-privileges`，恢复采用 `pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error`。
- 二进制 dump 先写入容器文件，再用 `docker cp` 导出，避免 Windows PowerShell 旧版本重定向破坏二进制。
- 任何 destructive 命令前都要求确认目标主机、目标库和可回退备份。

## Compatibility And Trade-Offs

- 源 PostgreSQL 16.14 与目标 `pgvector/pgvector:pg16` 主版本一致，适合用 PostgreSQL 16 的 `pg_dump/pg_restore`。
- 单文件 HTML 比接入 React 少一个路由和权限面，但不会自动跟随管理后台主题；这是用户指定的离线可用性取舍。
- Navicat 菜单文字可能因 16/17/18 版本不同，手册同时描述常见中文名、英文名和功能目的。
- 现有 `.sql` 仅作为诊断证据保留；不提供脆弱的正则清洗方案，因为扩展对象、identity sequence、依赖顺序和非原子执行同时存在。

## Rollback

HTML 是新增文件，删除即可回滚。数据库恢复的回滚依赖操作前制作的目标库备份；失败后保持写服务停止，重新创建空库并从已验证备份恢复，禁止在半恢复状态继续执行。
