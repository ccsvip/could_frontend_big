# ASR Settings Design

## Goal

Implement ASR management from `wiki/asr-websocket-tutorial.md` using Aliyun Qwen-ASR Realtime over a backend-managed WebSocket connection.

The platform has one global ASR configuration. Super administrators can configure it from `Settings > ASR Settings`. Company administrators and employees can open `AI Models > ASR Management`, see only the current status, and run a connection test. They cannot view or edit secrets.

## Configuration

`backend/.env` will use the new tutorial variables and remove the old `ALIYUN_ASR_*` variables:

- `MULTIMODAL_WORKSPACE_ID`
- `MULTIMODAL_API_KEY`
- `ASR_BASE_URL`
- `ASR_MODEL`

The initial values are the Beijing endpoint, the provided workspace ID/API key, and `qwen3-asr-flash-realtime`.

`ASR_BASE_URL` is the full Beijing WebSocket base URL without the `model` query string:

```text
wss://dashscope.aliyuncs.com/api-ws/v1/realtime
```

The backend appends `?model=<ASR_MODEL>` when connecting.

## Backend

Add a platform ASR settings API under `/api/v1/settings/asr/`:

- `GET /settings/asr/`: superuser only, returns editable settings with API key masked.
- `PATCH /settings/asr/`: superuser only, updates settings. Empty API key means keep the current value.
- `POST /settings/asr/test/`: authenticated users with ASR view permission can test the current ASR config.
- `GET /ai-models/asr/status/`: authenticated users with ASR view permission can read a non-secret status payload.
- `POST /ai-models/asr/test/`: same behavior as settings test, for company-side UI.

Settings are stored in a singleton model so the web UI can edit them without rewriting `.env`. If the singleton row does not exist, the service falls back to environment variables.

The ASR test opens the Aliyun WebSocket with:

- `Authorization: Bearer <MULTIMODAL_API_KEY>`
- `OpenAI-Beta: realtime=v1`
- `X-DashScope-WorkSpace: <MULTIMODAL_WORKSPACE_ID>`

It sends a minimal `session.update`, then `session.finish`. A successful handshake plus a parseable server event counts as success. Secrets are never returned in API responses.

## Permissions And Menus

Reuse the existing ASR view permission for company-side access:

- `ai_models.asr.view`: status and test.

Add superuser-only permissions/classes for settings endpoints using `IsSuperUser`; no company role can update ASR settings.

Add an `ASR Settings` child under the existing super-admin `Settings` menu in the frontend. Company users continue to use the existing `AI Models > ASR Management` entry.

## Frontend

Add `web/src/api/modules/asr.ts` for ASR settings, status, and test calls.

Add `web/src/views/asr-settings/index.tsx` for super administrators:

- status card
- editable fields for workspace ID, API key, base URL, model, enabled
- save and test actions

Replace the ASR placeholder page with a read-only management page:

- status tag
- endpoint/model summary without secrets
- test button and latest test result

## Validation

Backend tests cover:

- superuser can read/update ASR settings
- non-superuser cannot update settings
- users with `ai_models.asr.view` can read status and test
- status/test responses never expose the API key
- WebSocket test success/failure is isolated with mocks

Frontend validation runs inside Docker:

- `docker compose exec web npm run build`

Backend validation runs inside Docker:

- `docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api`
