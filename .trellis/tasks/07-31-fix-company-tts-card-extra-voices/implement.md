# Implementation Plan

1. Add an Aliyun-scoped data migration with the explicit 54-code denylist and no-op reverse.
2. Add focused migration cleanup tests proving exact-match deletion, canonical voice preservation, and cross-provider preservation.
3. Change the company TTS voice catalog body from `options.voices` to `availableVoices`.
4. Run the focused Django test module in Docker with `--keepdb`.
5. Apply migrations in Docker and query counts: Aliyun 48, legacy Loong 0, CosyVoice unchanged.
6. Run `python manage.py migrate --check` and `python manage.py makemigrations --check --dry-run` in Docker.
7. Run `npm run build` in `web/`.
8. Run GitNexus `detect_changes` and review affected symbols/flows.

## Risk Gates

- Before deletion, verify all 54 explicit codes still have zero tenant-default, device, and device-application references.
- Abort cleanup if the candidate set differs from the approved 54-code set.
- Never delete by `startswith`, regex, display name, numeric ID, or provider-independent query.

## Rollback Point

Before applying the migration, the current database is the rollback boundary. The migration reverse is intentionally a no-op; operational rollback requires restoring the database backup because the invalid rows have no repository-owned source of truth.
