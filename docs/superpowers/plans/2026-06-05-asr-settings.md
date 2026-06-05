# ASR Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build global ASR settings, status, and connection testing for Aliyun Qwen-ASR Realtime.

**Architecture:** Store a singleton `ASRConfig` row with environment fallback. Backend owns all WebSocket calls so secrets never reach browsers. Superusers edit settings under `/settings/asr/`; company users only read status and run tests under `/ai-models/asr/`.

**Tech Stack:** Django 5.2, DRF, SimpleJWT permissions, `websocket-client`, React 18, Vite, TypeScript, Ant Design.

---

## File Structure

- Modify `backend/.env`: remove old `ALIYUN_ASR_*`; add `MULTIMODAL_WORKSPACE_ID`, `MULTIMODAL_API_KEY`, `ASR_BASE_URL`, `ASR_MODEL`.
- Modify `backend/requirements.txt`: add `websocket-client` if missing.
- Modify `backend/config/settings/base.py`: expose new ASR settings constants.
- Modify `backend/apps/accounts/permissions.py`: add `CanViewASR`.
- Modify `backend/apps/ai_models/models.py`: add singleton `ASRConfig`.
- Create `backend/apps/ai_models/migrations/0007_asr_config.py`: create model and refresh ASR access data.
- Create `backend/apps/ai_models/services/asr.py`: build effective config, mask secrets, build URL, run WebSocket test.
- Modify `backend/apps/ai_models/serializers.py`: add ASR settings serializer.
- Modify `backend/apps/ai_models/views.py`: add ASR settings/status/test API views.
- Modify `backend/apps/ai_models/urls.py`: register ASR endpoints.
- Create `backend/apps/ai_models/tests/test_asr_api.py`: permission, masking, update, and mocked test coverage.
- Create `web/src/api/modules/asr.ts`: typed ASR API client.
- Create `web/src/views/asr-settings/index.tsx` and `web/src/views/asr-settings.ts`: superuser settings UI.
- Modify `web/src/views/asr-management/index.tsx`: replace placeholder with read-only status/test UI.
- Modify `web/src/router/index.tsx`: add `/settings/asr`.
- Modify `web/src/layouts/dashboard-layout.tsx`: add superuser settings menu item.

---

### Task 1: Backend ASR Config Model And Env

**Files:**
- Modify: `backend/.env`
- Modify: `backend/requirements.txt`
- Modify: `backend/config/settings/base.py`
- Modify: `backend/apps/ai_models/models.py`
- Create: `backend/apps/ai_models/migrations/0007_asr_config.py`

- [ ] **Step 1: Write model and env constants**

Add `ASRConfig` with fields `workspace_id`, `api_key`, `base_url`, `model`, `is_active`, `updated_at`, singleton `load()`, forced `pk=1`, and no-op `delete()`.

Add settings constants:

```python
MULTIMODAL_WORKSPACE_ID = os.getenv('MULTIMODAL_WORKSPACE_ID', '').strip()
MULTIMODAL_API_KEY = os.getenv('MULTIMODAL_API_KEY', '').strip()
ASR_BASE_URL = os.getenv('ASR_BASE_URL', 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime').strip()
ASR_MODEL = os.getenv('ASR_MODEL', 'qwen3-asr-flash-realtime').strip()
```

- [ ] **Step 2: Add migration**

Create `0007_asr_config.py` after `0006_chatconversation_tenant_llmprovider_tenant`. Include `ASRConfig` and an idempotent data migration ensuring `ai_models.asr.view` exists and `/ai-models/asr` remains an active `AI大模型` child menu.

- [ ] **Step 3: Update env and dependency**

Remove these old variables from `backend/.env`:

```env
ALIYUN_ASR_API_KEY
ALIYUN_ASR_API_URL
ALIYUN_ASR_MODEL
ALIYUN_ASR_SAMPLE_RATE
ALIYUN_ASR_AUDIO_FORMAT
```

Add:

```env
# aliyun qwen realtime asr
MULTIMODAL_WORKSPACE_ID=llm-imrcvsynd83s8f8b
MULTIMODAL_API_KEY=sk-8f1f4a70bda04dc48a2818a5491020a4
ASR_BASE_URL=wss://dashscope.aliyuncs.com/api-ws/v1/realtime
ASR_MODEL=qwen3-asr-flash-realtime
```

Ensure `websocket-client` is in `backend/requirements.txt`.

- [ ] **Step 4: Verify migration syntax**

Run:

```bash
docker compose exec backend python manage.py makemigrations --check
```

Expected: no unexpected model changes after the hand-written migration.

---

### Task 2: Backend ASR Service And API

**Files:**
- Modify: `backend/apps/accounts/permissions.py`
- Create: `backend/apps/ai_models/services/asr.py`
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/views.py`
- Modify: `backend/apps/ai_models/urls.py`
- Test: `backend/apps/ai_models/tests/test_asr_api.py`

- [ ] **Step 1: Write failing API tests**

Cover:

```python
def test_superuser_can_read_and_update_asr_settings()
def test_non_superuser_cannot_update_asr_settings()
def test_user_with_asr_view_can_read_status_without_secret()
def test_asr_test_uses_masked_response_and_mocked_success()
def test_asr_test_reports_missing_required_config()
```

Patch `apps.ai_models.services.asr.websocket.create_connection` for success/failure tests.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api
```

Expected: fail because endpoints/service do not exist yet.

- [ ] **Step 3: Implement permissions, service, serializers, views, urls**

Add `CanViewASR` requiring `ai_models.asr.view`.

Service functions:

```python
get_effective_asr_config()
serialize_asr_status()
build_asr_ws_url(config)
test_asr_connection()
```

Views:

- `ASRSettingsView`: `GET`, `PATCH`, `permission_classes = [IsSuperUser]`
- `ASRSettingsTestView`: `POST`, `permission_classes = [IsSuperUser]`
- `ASRStatusView`: `GET`, `permission_classes = [CanViewASR]`
- `ASRTestView`: `POST`, `permission_classes = [CanViewASR]`

- [ ] **Step 4: Run backend ASR tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api
```

Expected: all tests pass.

---

### Task 3: Frontend ASR Settings And Read-Only Management

**Files:**
- Create: `web/src/api/modules/asr.ts`
- Create: `web/src/views/asr-settings/index.tsx`
- Create: `web/src/views/asr-settings.ts`
- Modify: `web/src/views/asr-management/index.tsx`
- Modify: `web/src/router/index.tsx`
- Modify: `web/src/layouts/dashboard-layout.tsx`

- [ ] **Step 1: Add API client**

Export:

```ts
fetchAsrSettings()
updateAsrSettings(payload)
testAsrSettings()
fetchAsrStatus()
testAsr()
```

Types must not include raw secret fields in status responses.

- [ ] **Step 2: Add superuser settings page**

Build a compact Ant Design form with fields:

- `workspaceId`
- `apiKey`
- `baseUrl`
- `model`
- `isActive`

Use `apiKey` placeholder/masked value, save button, and test button. Empty API key keeps the backend value.

- [ ] **Step 3: Replace ASR management placeholder**

Show read-only cards for enabled status, model, endpoint host, workspace configured state, and a test button. Do not show API key.

- [ ] **Step 4: Wire route and menu**

Add lazy route `/settings/asr` guarded by `tenant.management.view`. Add `ASR设置` under superuser `设置`, next to `MinIO 设置`.

- [ ] **Step 5: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: TypeScript and Vite build pass.

---

### Task 4: Full Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api
```

Expected: all ASR API tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: build passes.

- [ ] **Step 3: Check git diff for secrets and scope**

Run:

```bash
git diff -- backend/.env backend/apps web/src
```

Expected: old ASR variables removed, new ASR variables present as requested, no ASR API response returns raw `MULTIMODAL_API_KEY`.
