# 数据库备份恢复兼容性实施计划

## Ordered Work

1. 读取 PostgreSQL custom dump 的恢复清单，确认它是可读归档；不再把 `.nb3` 作为自动化输入。
2. 新增 `scripts/verify-db-restore-upgrade.sh`：创建随机临时数据库、恢复 `BASELINE_DUMP`、以临时 `DATABASE_URL` 执行 Django migration 检查，并通过 trap 清理。
3. 更新 `.gitignore`，排除 Navicat `.nb3` 与 PostgreSQL custom `.dump` 归档，防止真实数据进入版本库。
4. 更新 `database-restore-guide.html`：增加“遗留 NB3 一次性导入 → 生成 canonical dump → 基线升级验证”的闭环；明确主库恢复和验证库是两个不同生命周期。
5. 在停止 backend、celery_worker、celery_beat 后，按已核验 schema 将当前开发库的 `ai_models.0036` 标记为 fake，执行真实 migration 至当前版本。
6. 使用新的 canonical dump 对隔离临时数据库运行脚本；确认所有 migration、模型同步检查和清理均成功。
7. 复查变更只涉及恢复兼容性脚本、忽略规则和恢复手册；检查用户的 `.nb3` 未被纳入版本控制。

## Validation

```bash
BASELINE_DUMP=/protected/path/digital_human-baseline.dump \
  ./scripts/verify-db-restore-upgrade.sh

docker compose run --rm --no-deps backend \
  python manage.py showmigrations --plan

docker compose ps
```

The script itself must assert:

- `pg_restore -l` accepts the archive;
- restore exits zero;
- `migrate --noinput` exits zero;
- `migrate --check` exits zero;
- `makemigrations --check --dry-run` exits zero;
- temporary database and copied archive are removed even when a previous stage fails.

## Risk Gates

- Never run the verifier against `POSTGRES_DB`; the script must reject a generated name equal to it.
- Do not run `--fake` in a general restore path; apply it only to the already inspected local 0036 drift.
- Do not modify, delete, rename, or squash historical migration files.
- Do not commit `.nb3`, `.dump`, or real business rows.
