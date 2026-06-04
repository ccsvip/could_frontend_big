# MinIO Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add platform-level MinIO settings and tenant-isolated video direct upload.

**Architecture:** MinIO connection settings are platform-level and editable only by super administrators. Tenant isolation is enforced by Django tenant resolution, tenant-scoped `Resource` rows, and server-generated object keys under `tenants/<tenant_id>/...`; clients never choose cross-tenant object keys.

**Tech Stack:** Django 5.2, DRF, MinIO Python SDK, React 18, Vite, Ant Design 5, Docker Compose.

---

### Task 1: Backend MinIO Model, Admin, Service, and Tests

**Files:**
- Modify: `backend/apps/resources/models.py`
- Modify: `backend/apps/resources/admin.py`
- Create: `backend/apps/resources/services/minio_client.py`
- Create: `backend/apps/resources/tests/test_minio_client.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Write failing service tests**

Create tests that assert `Resource.has_file` is true with `object_key`, MinIO object keys include the tenant id prefix, and cross-tenant object keys are rejected.

- [ ] **Step 2: Run tests to verify RED**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_client`

Expected: tests fail because `object_key`, `MinioConfig`, and service helpers do not exist.

- [ ] **Step 3: Implement model and service**

Add `Resource.object_key`, `MinioConfig` singleton, and service helpers for settings loading, key generation, public URL building, upload config, presign payloads, and safe deletion.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_client`

Expected: tests pass.

### Task 2: Backend API and Tenant Enforcement

**Files:**
- Modify: `backend/apps/resources/serializers.py`
- Modify: `backend/apps/resources/views.py`
- Modify: `backend/apps/resources/urls.py`
- Create: `backend/apps/resources/tests/test_minio_video_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests for upload config, presign object key tenant prefix, resource creation with matching object key, and rejection of another tenant's object key.

- [ ] **Step 2: Run tests to verify RED**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_video_api`

Expected: tests fail because MinIO video endpoints and serializer fields are missing.

- [ ] **Step 3: Implement API**

Add `/resources/videos/upload-config/` and `/resources/videos/presign/`, wire them in `urls.py`, and update `ResourceSerializer` to read/write `objectKey` while deriving playback URL from current MinIO settings.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_video_api`

Expected: tests pass.

### Task 3: Super Admin MinIO Settings API

**Files:**
- Create: `backend/apps/resources/tests/test_minio_settings_api.py`
- Modify: `backend/apps/resources/serializers.py`
- Modify: `backend/apps/resources/views.py`
- Modify: `backend/apps/resources/urls.py`

- [ ] **Step 1: Write failing settings API tests**

Add tests that superuser can GET/PATCH settings and a normal tenant user cannot.

- [ ] **Step 2: Run tests to verify RED**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_settings_api`

Expected: tests fail because settings API is missing.

- [ ] **Step 3: Implement settings API**

Expose a platform-level `/settings/minio/` endpoint guarded by `IsSuperUser`; do not scope it by tenant and do not return secret values unless needed for editing semantics.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_settings_api`

Expected: tests pass.

### Task 4: Frontend Settings Page and Video Direct Upload

**Files:**
- Modify: `web/src/api/modules/resources.ts`
- Create: `web/src/api/modules/settings.ts`
- Create: `web/src/views/minio-settings/index.tsx`
- Modify: `web/src/layouts/dashboard-layout.tsx`
- Modify: `web/src/router/index.tsx`
- Modify: `web/src/views/resource-management/index.tsx`
- Create/modify: `web/scripts/test-minio-settings-static.mjs`

- [ ] **Step 1: Write failing static tests**

Add static tests for the super-admin settings menu, route guard, MinIO settings API module, and video direct-upload objectKey payload.

- [ ] **Step 2: Run tests to verify RED**

Run: `docker compose exec web node web/scripts/test-minio-settings-static.mjs`

Expected: tests fail because the page, route, and upload functions are missing.

- [ ] **Step 3: Implement frontend**

Add a super-admin “设置 / MinIO 设置” menu, route `/settings/minio`, settings form UI, and video direct upload flow copied from the non-tenant project but using tenant-scoped backend presign behavior.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `docker compose exec web node web/scripts/test-minio-settings-static.mjs`

Expected: tests pass.

### Task 5: Environment and Verification

**Files:**
- Modify: `backend/.env`

- [ ] **Step 1: Configure environment**

Add MinIO endpoint, access key, secret key, bucket, secure flag, and video max-size variables to `backend/.env`. Do not hard-code secrets in source files.

- [ ] **Step 2: Run targeted backend tests**

Run: `docker compose exec backend python manage.py test apps.resources.tests.test_minio_client apps.resources.tests.test_minio_video_api apps.resources.tests.test_minio_settings_api`

Expected: all targeted backend tests pass.

- [ ] **Step 3: Run frontend verification**

Run: `docker compose exec web npm run lint`

Expected: lint passes.

- [ ] **Step 4: Run migrations check**

Run: `docker compose exec backend python manage.py makemigrations --check`

Expected: no pending model changes after committed migration exists.
