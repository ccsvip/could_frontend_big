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

(To be filled by the team)

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

<!-- Database-related mistakes your team has made -->

(To be filled by the team)
