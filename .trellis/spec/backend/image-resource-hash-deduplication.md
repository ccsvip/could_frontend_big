# Image Resource Hash Deduplication

## 1. Scope / Trigger

Apply this contract to every path that creates an image `Resource`: multipart single upload,
multipart bulk upload, and R2 direct upload. Video resources are excluded. The rule prevents
duplicate storage without exposing or sharing data across tenants.

## 2. Signatures

- Database key: unique `(tenant, content_hash)` when `resource_type='image'` and `content_hash != ''`.
- API field: `contentHash`, a lowercase 64-character SHA-256 hexadecimal string.
- Duplicate locator: `data.existingResource` with `id`, `category`, and
  `isDigitalHumanBackground` for the current tenant's existing image.
- Presign: `POST /api/v1/resources/presign/` requires `contentHash` for images only.
- Bulk upload: `POST /api/v1/resources/images/bulk/`.
- Backfill: `python manage.py backfill_image_content_hashes`.

## 3. Contracts

Multipart uploads calculate SHA-256 from the received bytes on the backend. R2 clients calculate
SHA-256 before requesting a presigned URL and send the same `contentHash` when creating the
resource. Client hashes are an upload optimization; tenant scope and the database constraint are
the final authorization and concurrency boundaries.

Bulk responses always use this shape:

```json
{
  "created": [],
  "duplicates": [{"fileName": "copy.png", "reason": "该图片已存在"}]
}
```

Single-image and presign duplicate conflicts use the global error envelope and include a locator:

```json
{
  "status": "error",
  "message": "该图片已存在",
  "code": 409,
  "data": {
    "existingResource": {
      "id": 123,
      "category": "horizontal",
      "isDigitalHumanBackground": false
    }
  }
}
```

After this conflict, the resource page closes the upload dialog, clears the keyword, switches to
the existing image's category and usage, resets pagination to page 1, and reloads immediately.
The locator describes the stored resource, not values from the rejected request.

The backfill command processes empty hashes in `created_at,id` order. The earliest resource keeps
the hash; later duplicates remain unindexed and are reported. No resource or reference is deleted.

## 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Missing or malformed image `contentHash` on presign/R2 create | HTTP 400, field `contentHash` |
| Hash already exists for the current tenant | HTTP 409 with `data.existingResource` for the stored image |
| Same hash exists only for another tenant | Allowed; no foreign resource data returned |
| Bulk request mixes new and duplicate files | New files created, duplicates listed, HTTP 201 |
| Entire bulk request is duplicate | No files created, duplicates listed, HTTP 200 |
| Concurrent same-tenant create | Database constraint permits one resource only |
| Backfill cannot read one object | Report `FAILED`, continue processing |

## 5. Good / Base / Bad Cases

- Good: compute the multipart hash from server-received bytes and reset the file position.
- Base: leave historical hashes empty until the idempotent command reads the actual file/object.
- Bad: trust only a browser-side `Set`, query without tenant scope, or access object storage in a migration.
- Bad: show only a duplicate toast while leaving the list under filters that hide the stored image.

## 6. Tests Required

- Assert first upload stores the exact SHA-256 and renamed duplicate content returns 409.
- Assert the 409 locator contains the stored image's ID, category, and usage even when the rejected
  request submits different values.
- Assert same hash is allowed across tenants and for video resources.
- Assert bulk upload preserves new items while listing database and in-request duplicates.
- Assert image presign validates the hash, remains tenant-scoped, and video presign needs no hash.
- Assert an unreferenced R2 object key is deleted after a duplicate conflict.
- Assert object streaming closes/releases the response and backfill is idempotent, tolerant, and earliest-first.

## 7. Wrong vs Correct

### Wrong

```python
Resource.objects.filter(content_hash=content_hash).exists()
```

This leaks a cross-tenant existence signal and does not stop concurrent inserts.

### Correct

```python
Resource.objects.filter(
    tenant=tenant,
    resource_type=Resource.TYPE_IMAGE,
    content_hash=content_hash,
).exists()
```

Keep this tenant-scoped precheck for a clear error, and retain the conditional database unique
constraint as the concurrency guarantee.

On the frontend, parse the locator once in the resource API module and use the typed result to
update page filters. Do not cast the Axios payload independently in the page component.
