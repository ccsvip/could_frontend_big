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

<!-- How to create and run migrations -->

(To be filled by the team)

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

<!-- Database-related mistakes your team has made -->

(To be filled by the team)
