# Image Resource Bulk Delete

## 1. Scope / Trigger

Use this contract when deleting multiple company-scoped image `Resource` records from the resource management UI. It does not apply to videos or cross-page selection.

## 2. Signatures

```http
DELETE /api/v1/resources/images/bulk/
Content-Type: application/json
Authorization: Bearer <token>

{"ids": [12, 15, 19]}
```

The frontend consumer is `bulkDeleteImageResources(ids: number[])` in `web/src/api/modules/resources.ts`.

## 3. Contracts

- `ids`: 1-100 unique positive integer resource IDs.
- Permission: `resources.images.delete` through `CanDeleteImageResources`.
- Scope: resolve candidates only through `ImageResourceViewSet.get_queryset()` so resource type and tenant scope remain enforced.
- Result: partial success; valid deletions are not rolled back when another ID fails.
- Storage: `perform_destroy()` must snapshot `file.name` and `file.storage` before deleting the model, then delete the stored file after the database deletion succeeds. Django does not delete `FileField` content when a model is deleted.
- Object storage: resources with `object_key` continue to call `delete_object(object_key, backend=storage_backend)` after database deletion.

```json
{
  "deletedIds": [12, 15],
  "failures": [
    {"id": 19, "name": "Referenced image", "reason": "该资源被 1 个标注回复引用，不能删除"}
  ]
}
```

## 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Missing/empty `ids`, non-integer, non-positive, duplicate, or more than 100 IDs | `400` |
| Missing delete permission | `403` |
| Visible deletable image | ID added to `deletedIds` |
| Visible image with a `FileField` upload | Database row and stored file are both deleted |
| Referenced visible image | Item added to `failures` with the reference reason |
| Missing, other-tenant, or non-image ID | Failure with empty `name` and `图片不存在或无权访问` |

## 5. Good / Base / Bad Cases

- Good: mixed valid and referenced IDs delete valid images and report referenced images.
- Base: all valid current-page IDs return in `deletedIds` with no failures.
- Bad: querying `Resource.objects.filter(id__in=ids)` without tenant-scoped `get_queryset()` can delete another company's data.

## 6. Tests Required

- Assert partial success preserves the referenced image and deletes the valid image.
- Assert other-tenant, video, and unknown IDs are not deleted and share the non-disclosing failure message.
- Assert requests without delete permission return `403`.
- Assert duplicate IDs return `400`.
- Prime the resources business cache before deletion and assert the refreshed list reflects deletions.
- Create a real file under a temporary `MEDIA_ROOT`, call the bulk delete API, and assert both `Resource.objects.filter(id=...).exists()` and `Path(file_path).exists()` are false.

## 7. Wrong vs Correct

Wrong:

```python
resources = Resource.objects.filter(id__in=ids)
resources.delete()
```

Correct:

```python
resources = {item.id: item for item in self.get_queryset().filter(id__in=ids)}
for resource_id in ids:
    resource = resources.get(resource_id)
    if resource is not None:
        self.perform_destroy(resource)
```

The correct path preserves tenant isolation, image-only scope, reference protection, storage cleanup, and cache invalidation.

Wrong:

```python
super().perform_destroy(instance)  # FileField content remains on storage.
```

Correct:

```python
file_name = instance.file.name if instance.file else ''
file_storage = instance.file.storage if file_name else None
super().perform_destroy(instance)
if file_name and file_storage is not None:
    file_storage.delete(file_name)
```
