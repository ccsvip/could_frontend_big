# 数据库备份恢复兼容性设计

## Problem Boundary

`20260727173331.nb3` 是 Navicat 私有归档，不能由 PostgreSQL 工具直接恢复或在自动化中验证。其 schema 与 `django_migrations` 记录停留在稳定的 0035 基线；当前目标库的 0036 重复表来自恢复目标污染，而非备份。

兼容性承诺从一个标准 PostgreSQL custom-format 基线开始：该基线必须恢复到一次性、独立的临时数据库，然后以当前代码运行全部 Django migration。生产/开发主库不参与验证。

## Canonical Backup Contract

1. 一次性通过 Navicat 将遗留 `.nb3` 恢复到真正的空库；恢复期间只启动 `db` 和必要的 `redis`，不启动 backend/Celery。
2. 在迁移记录与 schema 一致的该库中，使用 PostgreSQL 16 容器内的 `pg_dump -Fc --no-owner --no-privileges` 生成 custom-format 基线。
3. 基线归档不进 Git；存放于受保护制品库或本地安全路径，以 `BASELINE_DUMP` 注入验证命令。
4. 任何新增、删除、重命名字段，或包含数据变换的 migration，在合并/发布前必须通过基线升级验证。历史 migration 不删除、不改写、不 squash。

## Verification Design

新增 `scripts/verify-db-restore-upgrade.sh`：

- 必须接收绝对或相对的 `BASELINE_DUMP`；先检查文件存在且能被 PostgreSQL 16 `pg_restore -l` 读取。
- 只要求 Compose `db` 已健康；不启动 backend、Celery、web 或 Caddy 的常规服务命令。
- 在 `db` 容器中创建带固定安全前缀、带时间与 PID 后缀的临时数据库；绝不使用或删除 `POSTGRES_DB` 主库。
- 将 dump 拷贝至 db 容器，以 `pg_restore --exit-on-error --no-owner --no-privileges` 恢复；任何 restore 错误立即失败。
- 用 `docker compose run --rm --no-deps backend` 覆盖 `DATABASE_URL` 的最后一个数据库 path segment，连接临时库并运行：`migrate --noinput`、`migrate --check` 与 `makemigrations --check --dry-run`。
- 脚本在任何成功或失败路径中删除容器内归档与临时数据库；主库、卷和业务服务不受影响。

这个验证覆盖“旧 schema + 真实基线数据 + 当前 migration”这一实际升级路径；它不声称可从损坏的 restore 目标自动推断或修复迁移状态。

## Current Database Repair

当前库中 `ai_models_asrfillerwordset` 的字段与 0036 完整匹配，且旧 `filter_filler_words` 已不存在。修复应在写服务停止后，先记录 0036 为 fake，再正常执行所有后续 migration。该修复是针对已核验的本地库，不纳入恢复流程的通用自动化。

## Rollback and Safety

- 验证脚本失败：保留标准 dump，不触碰主库；读取输出后修复当前 migration，再重新运行。
- 实际恢复失败：保持写服务停止，重新创建空库并重新恢复；禁止在半恢复库上手工补 DDL 或无限重试。
- 若未来 migration 无法通过真实基线验证，则该 migration 不可发布。
