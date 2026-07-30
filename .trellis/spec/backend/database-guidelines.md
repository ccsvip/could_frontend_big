# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

<!--
Document your project's database conventions here.

Questions to answer:
- What ORM/query library do you use?
- How are migrations managed?
- What are the naming conventions for tables/columns?
- How do you handle transactions?
-->

(To be filled by the team)

---

## Query Patterns

### Immutable (Append-Only) Event Models

For audit-critical event data (status reports, state transitions, telemetry), use an append-only model pattern. Events are inserted but never updated or deleted through business APIs.

```python
class AppUpdateEvent(models.Model):
    device = models.ForeignKey(Device, ...)
    release = models.ForeignKey(AppRelease, null=True, ...)
    package_name = models.CharField(max_length=255)
    # ... other fields

    class Meta:
        verbose_name = "应用升级事件"
        # No update or delete permissions for business API
```

| Operation | Business API | Admin | Database |
|-----------|-------------|-------|----------|
| Create | ✅ POST /report/ | ✅ Admin read-only | INSERT |
| Read | ❌ | ✅ | SELECT |
| Update | ❌ | ❌ | ❌ |
| Delete | ❌ | ❌ (Admin list editable must be False) | ❌ |

**Why**: Event immutability provides a reliable audit trail. Status reports from devices cannot be tampered with or lost due to accidental updates.

### Immutable Release Models

For content publishing (releases, artifacts, documents), use an immutable model where only the `is_active` / soft-toggle field is mutable after creation. Computed fields (hash, size, ID) are set at creation and never change.

```python
class AppRelease(models.Model):
    release_id = models.CharField(max_length=64, unique=True, editable=False)
    apk_file = models.FileField(upload_to="app_updates/")
    sha256 = models.CharField(max_length=64, editable=False)
    file_size = models.BigIntegerField(editable=False)
    is_active = models.BooleanField(default=True)  # ← only mutable field

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.release_id = generate_uuid()
            self.sha256 = compute_sha256(self.apk_file)
            self.file_size = self.apk_file.size
        super().save(*args, **kwargs)
```

**Constraints**:
- Non-`is_active` fields are `editable=False` in the model
- Admin change form makes non-toggle fields read-only
- No `PUT`/`DELETE` endpoints in the ViewSet
- Serializer explicitly excludes hash/size/ID from write fields

**Why**: Published artifacts represent a contract with clients. Allowing edits or deletes would break verification (signature validation, hash matching) and potentially strand devices with references to invalid releases.

---

## Migrations

### Scenario: Reconcile a Restored Database with Migration History

#### 1. Scope / Trigger

- Trigger: `migrate` fails with `DuplicateTable`, `DuplicateColumn`, or a duplicate primary key after a database restore, branch switch, or schema import.
- This procedure applies to development and preserved `--keepdb` test databases. Never use it against production without a reviewed backup and recovery plan.

#### 2. Signatures

```bash
docker compose exec backend python manage.py showmigrations <app>
docker compose exec backend python manage.py sqlmigrate <app> <migration>
docker compose exec backend python manage.py migrate <app> <migration> --fake
docker compose exec backend python manage.py migrate --check
```

Sequence repair uses the exact table and primary key column:

```sql
SELECT setval(
  pg_get_serial_sequence('<table>', 'id'),
  COALESCE(MAX(id), 1),
  MAX(id) IS NOT NULL
) FROM <table>;
```

#### 3. Contracts

- `--fake` is allowed only after the existing columns, types, nullability, identity/default behavior, indexes, foreign keys, unique constraints, and check constraints match `sqlmigrate`.
- If a migration is only partially reflected in the database, execute the missing SQL first and fake the migration only after its complete final state is present.
- Preserve business rows and existing volumes. Do not drop a development or test database merely to bypass migration drift.
- Run tests that share a `--keepdb` database serially; concurrent migration setup can race and report false duplicate-column failures.

#### 4. Validation & Error Matrix

| Condition | Required action |
|-----------|-----------------|
| Table/column exists and the full migration effect matches | Fake that migration, then continue normally |
| Only part of the migration effect exists | Apply only the missing operations, verify, then fake |
| Existing structure differs from the migration | Stop; do not fake until the mismatch and data compatibility are resolved |
| Insert fails on an existing primary key | Compare the sequence value with `MAX(id)` and repair the exact sequence |
| `migrate --check` is non-zero | Do not start dependent services or declare the repair complete |

#### 5. Good/Base/Bad Cases

- Good: a restored table exactly matches `sqlmigrate`; fake its missing record and run all later migrations normally.
- Base: no drift exists; run `docker compose exec backend python manage.py migrate` without special handling.
- Bad: use `--fake` immediately after seeing `DuplicateTable`, leaving other operations from the same migration unapplied.

#### 6. Tests Required

- Assert `migrate --check` exits successfully.
- Assert `makemigrations --check --dry-run` reports `No changes detected`.
- Run the affected Django test module with `--keepdb` and assert test database setup completes before the test cases run.
- Restart Compose and assert the backend health check, Celery ping, and an authenticated or authentication-protected API response.

#### 7. Wrong vs Correct

Wrong:

```bash
# The duplicate table proves only that one operation already exists.
python manage.py migrate ai_models 0036 --fake
```

Correct:

```bash
python manage.py sqlmigrate ai_models 0036
# Compare every operation with information_schema/pg_constraint, apply any
# missing operation, then record the fully represented migration.
python manage.py migrate ai_models 0036 --fake
python manage.py migrate --check
```

### Scenario: Verify a Preserved Backup Can Upgrade

#### 1. Scope / Trigger

- Trigger: before merging any schema or data migration, when replacing a development database, or after a legacy Navicat restore.
- Use a PostgreSQL custom-format archive created by `pg_dump -Fc`; Navicat `.nb3` is a one-time GUI import source, not an automated restore format.

#### 2. Contracts

- Keep the protected baseline archive outside Git and provide it with `BASELINE_DUMP`.
- Run `bash scripts/verify-db-restore-upgrade.sh` with only Compose `db` healthy. It must restore into a generated `restore_verify_*` database, run `migrate --noinput`, `migrate --check`, and `makemigrations --check --dry-run`, then remove the database and copied archive on both success and failure.
- The verifier must not connect to, restore into, migrate, or drop `POSTGRES_DB`; backend, Celery worker, and Celery beat remain stopped until the isolated verification succeeds.
- After a Navicat restore, reconcile every public identity/serial sequence to its table maximum before any data migration can insert rows. A stale sequence can surface as a duplicate primary key in an unrelated `RunPython` migration.
- A `DuplicateTable` migration record and stale sequences are independent forms of drift. Verify the full schema before `--fake`, then reconcile the affected sequence(s) before resuming migrations.

#### 3. Validation

- Smoke-test the verifier with a disposable `pg_dump -Fc` archive and assert no `restore_verify_*` database remains.
- The actual acceptance path is the preserved old baseline upgrading to the current checkout; a current-schema dump proves script plumbing only.
- Do not start Compose writers until the target database finishes `migrate --noinput`, `migrate --check`, and `makemigrations --check --dry-run`.

### Scenario: Backfill a Grant Table When Tightening Access

#### 1. Scope / Trigger

- Trigger: adding an authorization table that gates something previously open to
  everyone (for example `TenantTTSProviderGrant`, see
  [TTS Tenant Card Authorization](./tts-tenant-card-authorization.md)).
- Without a backfill, deploying the tightened read path revokes every existing
  tenant at once.

#### 2. Contracts

- Ship the schema migration and the data migration as **separate** files, in order.
- The data migration grants only what was already implicitly available. It must not
  hand out anything new — a newly added vendor/card stays ungranted until an admin
  allocates it explicitly.
- Use `update_or_create` so the migration is idempotent and safe to re-run against a
  partially migrated database.
- Return early when the prerequisite row is absent (fresh database, seeds not yet
  applied), rather than raising.
- Scope the backfill to live records only (e.g. `is_active=True` tenants).
- Provide a reverse function that removes only the rows this migration created.
- Migrate legacy config into the new per-owner column while it is being written, so
  the old single-JSON column can stop being the authority.

```python
def seed_grants(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Provider = apps.get_model('ai_models', 'TTSProvider')
    Grant = apps.get_model('ai_models', 'TenantTTSProviderGrant')

    provider = Provider.objects.filter(code='aliyun').first()
    if provider is None:
        return                                  # fresh DB: nothing to backfill
    for tenant_id in Tenant.objects.filter(is_active=True).values_list('id', flat=True):
        Grant.objects.update_or_create(         # idempotent
            tenant_id=tenant_id, provider_id=provider.id,
            defaults={'is_active': True, 'public_config': legacy_config_for(tenant_id)},
        )
```

#### 3. Validation

- `makemigrations --check --dry-run` reports `No changes detected`.
- Run `migrate`, then query the table and confirm the row count matches the number of
  live owners and that legacy config actually carried over. A green migration is not
  evidence the backfill was correct.
- Re-run `migrate` (or the `RunPython` twice) and confirm no duplicate-key error.

#### 4. Test Impact (expect this)

Tightening a read path **will** break existing tests that create the owning record
directly, because those records hold no grant. Add the grant in the affected `setUp`.
That is the correct consequence of the tightening — do not loosen the production
predicate to keep old tests green.

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

<!-- Database-related mistakes your team has made -->

(To be filled by the team)
