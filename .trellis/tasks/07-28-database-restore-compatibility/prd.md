# 数据库备份恢复兼容性

## Goal

让已保存的数据库基线能够在未来项目版本中恢复到干净数据库，并通过 Django 迁移升级到当前 schema，不出现 schema 与 `django_migrations` 记录分叉。

## Confirmed Facts

- `20260727173331.nb3` 是 Navicat 30.1 PostgreSQL 备份：POSIX tar 容器、`DatabaseType=PGSQL`、库名 `digital_human`，不是 PostgreSQL `pg_restore` 可读的 custom-format dump。
- 该备份的 `django_migrations` 有 176 条记录；其中 `ai_models` 最后为 `0035_agent_application_tts_filter_exclude_patterns`。
- 备份中没有 `ai_models_asrfillerwordset`；该表却存在于当前目标库而 `ai_models.0036_asr_filler_word_set` 没有记录。因此重复表不是该备份直接造成的，目标库在恢复前或恢复期间被污染。
- `backend` 每次启动都会依次执行 `migrate`、周期任务种子、静态文件收集、管理员创建和设备种子。`celery_worker` 与 `celery_beat` 依赖 backend 健康，因此恢复时必须只启动基础数据库服务。

## Requirements

- R1：交付一条可重复的恢复链路：旧基线备份恢复至空库后，当前代码的完整 Django migration 正常完成。
- R2：恢复期间禁止 backend、celery_worker、celery_beat 对目标库执行 migration、种子或业务写入。
- R3：审查 Compose 启动链和 Django migration；只修复已证实会破坏恢复一致性的代码或配置问题。
- R4：保留全部历史 Django migration；未来 schema 变更必须能从本基线版本向前升级。
- R5：交付可自动执行的验证，能检测“基线恢复后无法迁移到当前代码”的回归。
- R6：针对当前已核验的开发库漂移，恢复 `ai_models.0036` 的迁移记录并正常升级，不重建业务数据。

## Acceptance Criteria

- [ ] 给出备份格式、目标库生命周期和服务启动顺序的可执行契约。
- [ ] 从基线备份恢复后的库不含 schema/迁移记录漂移；`migrate --check` 成功。
- [ ] 恢复验证能证明基线数据库可升级到当前仓库 migration 状态。
- [ ] 已证实的代码或配置缺陷被修复，并有针对性验证。
- [ ] 不修改历史 migration 来迁就已污染的目标库。
- [ ] 当前开发库的 `ai_models.0036` 漂移被按完整 schema 核验后修复，backend 能稳定启动。

## Key Decision

- 后续可恢复、可自动验证的基线格式固定为 PostgreSQL 16 `pg_dump -Fc` custom-format 归档。现有 `.nb3` 仅用于一次性 Navicat 遗留导入，导入成功后立即生成该标准归档。
- 完整基线归档不提交 Git；通过受保护的本地或 CI 制品路径以 `BASELINE_DUMP` 传入验证脚本。该脚本必须在发布或 schema/data migration 变更前运行。

## Migration Audit

- 备份基线之后共有 21 个待执行迁移：`ai_models` 0036–0042、`devices` 0020–0024、`app_updates` 0001、`knowledge_base` 0015、`resources` 0035–0041。
- 迁移审查未发现阻止该基线前向升级的既有代码缺陷：新增非空字段均有默认值，外键变更放宽了 nullable；唯一约束仅约束新字段的非空 hash；唯一 `RunPython` 以 `update_or_create` 和幂等 M2M 添加写入权限。
- `makemigrations --check --dry-run` 已返回 `No changes detected`。当前目标库的 0036 重复表是恢复污染，不能由修改历史 migration 修复。

## Scope

- 在范围内：修复当前已污染开发库的迁移记录、加入独立临时数据库的基线升级验证脚本、忽略本地备份归档、把实际恢复与验证步骤纳入现有恢复手册。
- 不在范围内：提交真实数据库数据、自动解析或替代 Navicat `.nb3`、修改既有业务模型或历史 migration、把媒体文件与 `.env` 当作数据库归档内容。
