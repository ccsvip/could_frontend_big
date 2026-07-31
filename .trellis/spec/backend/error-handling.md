# Error Handling

## Envelope Format (DRF)

All DRF exceptions pass through the global exception handler registered in
`config.exceptions.custom_exception_handler` (set via `EXCEPTION_HANDLER` in
`config/settings/base.py`).

### Error Response

```json
{"status": "error", "message": "...", "code": 400}
```

On exceptions that set `self.response_data`, an extra `data` key is included:

```json
{"status": "error", "message": "...", "code": 409, "data": {...}}
```

### Success Response

```json
{"status": "success", "message": "...", "data": {...}}
```

Minimal success (no data payload):

```json
{"status": "success", "message": "密码重置成功，员工下次登录需修改密码"}
```

Runtime-style success (includes `requestId`/`traceId` from the request middleware):

```json
{"status": "success", "message": "心跳成功", "requestId": "...", "traceId": "..."}
```

Static-resource / API success with explicit `code`:

```json
{"status": "success", "message": "success", "code": 200, "data": {...}}
```

### Exception: app_updates subsystem

The `apps.app_updates` module does **not** use the global envelope. Every view
constructs its own response via `_error_response()` and `_trace_payload()`,
yielding a different shape:

```json
{"requestId": "...", "traceId": "...", "code": "INVALID_REQUEST", "message": "..."}

# With optional details:
{"requestId": "...", "traceId": "...", "code": "INVALID_REQUEST", "message": "...", "details": {...}}
```

Non-error responses in app_updates use plain `_trace_payload()` data without
the `status`/`message`/`data` envelope shape.

## Handler (`config/exceptions.py`)

### Category Handler Map

| Category                 | HTTP Status | Source                                                                                                                                  |
|--------------------------|-------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `validation`             | 400         | `rest_framework.exceptions.ValidationError` — field errors joined with `；`                                                            |
| `permission`             | 403         | `rest_framework.exceptions.PermissionDenied`                                                                                            |
| `authentication`         | 401         | `AuthenticationFailed` / `NotAuthenticated`                                                                                             |
| `not_found`              | 404         | `rest_framework.exceptions.NotFound` / `django.http.Http404`                                                                            |
| `conflict`               | 409         | `DuplicateImageError` (custom `APIException` subclass)                                                                                  |
| `database_integrity`     | 400         | `django.db.IntegrityError` — special-cased phone-unique message; generic unique/duplicate message fallback                              |
| `django_validation`      | 400         | `django.core.exceptions.ValidationError` — messages joined with `；`                                                                   |
| `unhandled` (catch-all)  | 500         | Generic fallback: `"服务器内部错误，请稍后重试"`                                                                                        |

### Processing Logic

1. Delegate to `rest_framework.views.exception_handler` first.
2. If DRF returns a response (recognised exception):
   - Build `{"status":"error", "message":"...", "code":<status>}`
   - Copy `exc.response_data` into response `data` key if present.
   - Extract message from `response.data`:
     - `detail` key → use directly.
     - Field-name keys → join error strings with `；`, special-case phone duplicate.
     - List → join with `；`.
     - Fallback → `str(response.data)`.
3. If `django.db.IntegrityError`:
   - Phone duplicate → `"该手机号已提交过申请，请勿重复提交"`.
   - Generic unique constraint → `"数据重复，该记录已存在"`.
   - Other → `"数据保存失败，请检查输入信息"`.
   - Returns `{"status":"error","message":"...","code":400}` with 400 status.
4. If `django.core.exceptions.ValidationError`:
   - Messages joined with `；`.
   - Returns envelope with 400 status.
5. Unhandled → `{"status":"error","message":"服务器内部错误，请稍后重试","code":500}`.

### Phone-unique Special Case

When a `ValidationError` from DRF serializers contains `"手机号"` and `"已存在"`
in any field message, the exception handler rewrites it to `"该手机号已提交过申请，请勿重复提交"`.
The same message is produced by the `IntegrityError` handler when the error
string contains `"phone"` and `"已经存在"`.

## Custom Exception Classes

### `DuplicateImageError` (conflict — 409)

**File:** `backend/apps/resources/services/image_hashes.py`

```python
class DuplicateImageError(APIException):
    status_code = 409
    default_code = 'duplicate_image'
```

- Inherits from `rest_framework.exceptions.APIException` so the global handler
  catches it automatically.
- Constructor takes an existing `Resource` instance and sets `self.response_data`:
  ```python
  self.response_data = {
      'existingResource': {
          'id': existing_resource.id,
          'category': existing_resource.category,
          'isDigitalHumanBackground': existing_resource.is_digital_human_background,
      },
  }
  ```
- The `response_data` dict is injected into the envelope's `data` field by the
  global exception handler.
- Raised with `raise DuplicateImageError(duplicate)` where `duplicate` is a
  `Resource` query result.

### `RuntimeDeviceError` (non-DRF, for device-facing APIs)

**File:** `backend/apps/devices/services/runtime.py`

```python
@dataclass(slots=True)
class RuntimeDeviceError(Exception):
    message: str
    status_code: int
    code: str = 'DEVICE_RUNTIME_ERROR'
    business_status_code: int = 44000
```

- Inherits from base `Exception` — **not** caught by DRF's exception handler.
- Callers must catch and handle manually (see app_updates pattern below).
- Provides `as_payload()`:
  ```python
  def as_payload(self) -> dict[str, object]:
      return {
          'code': self.code,
          'statusCode': self.business_status_code,
          'message': self.message,
      }
  ```
- Pre-defined error constants in the same module use `(code, status_code)` tuples:
  `RUNTIME_ERROR_EMPTY_DEVICE_CODE`, `RUNTIME_ERROR_DEVICE_NOT_REGISTERED`,
  `RUNTIME_ERROR_DUPLICATE_DEVICE_CODE`, `RUNTIME_ERROR_DEVICE_UNBOUND_TENANT`,
  `RUNTIME_ERROR_TENANT_DISABLED`, `RUNTIME_ERROR_DEVICE_DISABLED`,
  `RUNTIME_ERROR_DEVICE_EXPIRED`, `RUNTIME_ERROR_AGENT_UNBOUND`,
  `RUNTIME_ERROR_APPLICATION_INACTIVE`.

## Scenario: Device Status Ping Runtime Errors

### 1. Scope / Trigger

- Applies to Android `device.status.ping` commands on the unified `/ws/realtime/` connection.
- A ping is a recoverable device heartbeat, not merely an assertion that `device.status.start` previously succeeded.

### 2. Signatures

- Command: `{"type":"device.status.ping","id":string,"payload":{"deviceCode":string,"requestId"?:string,"traceId"?:string}}`
- Resolver: `get_ready_runtime_device(device_code: str) -> Device`

### 3. Contracts

- Read `payload.deviceCode`; accept `payload.device_code` for compatibility.
- If the connection already owns a device-status session, a missing payload code may fall back to that session's device code.
- A ready device without an active status session is marked online, attached to the connection, and receives `device.status.pong`.
- Error responses preserve command `id` and include non-empty `requestId` / `traceId` correlation values.

### 4. Validation & Error Matrix

- Missing code -> `1001 DEVICE_CODE_REQUIRED`
- Unknown code -> `1002 DEVICE_NOT_REGISTERED`
- Unbound tenant -> `1004 DEVICE_TENANT_UNBOUND`
- Disabled tenant -> `1005 DEVICE_TENANT_DISABLED`
- Disabled device -> `1006 DEVICE_DISABLED`
- Expired authorization -> `1007 DEVICE_EXPIRED`
- Missing or inactive effective agent application -> `1008 DEVICE_AGENT_UNBOUND`
- Inactive bound device application -> `1009 DEVICE_APPLICATION_INACTIVE`

### 5. Good/Base/Bad Cases

- Good: a ready device sends ping before start and receives `device.status.pong`; disconnect marks it offline.
- Base: a started session sends ping and refreshes `last_heartbeat` after revalidation.
- Bad: a disabled device sends ping and receives `1006`, never the protocol-only `1017` fallback.

### 6. Tests Required

- WebSocket integration tests must assert ready-device recovery, exact business error code/message propagation, request/trace correlation, and online-to-offline lifecycle.
- Revalidate an established session after disabling its device and assert the next ping returns `1006` and clears online state.

### 7. Wrong vs Correct

#### Wrong

```python
if connection.device_status_device_id is None:
    return REALTIME_DEVICE_STATUS_NOT_STARTED
```

#### Correct

```python
device = get_ready_runtime_device(payload_device_code)
# Recover or refresh the connection, then return device.status.pong.
```

## Scenario: Pending Device Runtime Config Errors

### 1. Scope / Trigger

- Applies to `GET /api/v1/device-runtime/config/` after a previously unknown Android device calls the activation endpoint and creates a pending `Device` row.

### 2. Signatures

- Activation: `POST /api/v1/device-auth/activate/` with `deviceCode` creates a pending device when the code is unknown.
- Config: `GET /api/v1/device-runtime/config/` with `X-Device-Code` resolves the runtime configuration.

### 3. Contracts

- A pending row has `tenant_id=None`; it records the authorization request but is not yet runtime-registered.
- Runtime config maps this state to `{"code":"1002","statusCode":44004,"message":"设备未登记"}` with HTTP 404.
- A tenant-bound device with no active effective agent remains `1008 / 44021` with HTTP 403.

### 4. Validation & Error Matrix

- No row for device code -> `1002 DEVICE_NOT_REGISTERED`.
- Pending activation row with no tenant -> `1002 DEVICE_NOT_REGISTERED`.
- Tenant-bound row with no active effective agent -> `1008 DEVICE_AGENT_UNBOUND`.
- Tenant-bound, enabled, configured row -> full HTTP 200 runtime configuration.

### 5. Good/Base/Bad Cases

- Good: an authorized device receives its full runtime configuration.
- Base: a completely unknown code receives `1002`.
- Bad: a pending authorization request must not fall through to the agent check and report `1008`.

### 6. Tests Required

- Exercise activation followed by config and assert HTTP 404 plus exact `1002 / 44004 / 设备未登记` fields.
- Separately assert unknown-device `1002` and tenant-bound-without-agent `1008` to preserve the boundary.

### 7. Wrong vs Correct

#### Wrong

```python
agent_application = device.effective_agent_application
if agent_application is None:
    return DEVICE_AGENT_UNBOUND
```

#### Correct

```python
if device.tenant_id is None:
    return DEVICE_NOT_REGISTERED
# Only authorized tenant-bound devices reach application and agent validation.
```

### `AppUpdateSigningError` (service error — 503)

**File:** `backend/apps/app_updates/signing.py`

```python
class AppUpdateSigningError(RuntimeError):
    pass
```

- Inherits from `RuntimeError`.
- Caught explicitly in `apps.app_updates.views.AppUpdateCheckView.post` and
  returned as 503 via `_error_response()`:
  ```python
  _error_response(request, code='UPDATE_SIGNING_UNAVAILABLE',
                  message=str(exc), http_status=503)
  ```

### `TenantAwareJWTAuthentication` (auth — 401)

**File:** `backend/apps/accounts/authentication.py`

```python
class TenantAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        tenant = get_user_tenant(user)
        if tenant is not None and not tenant.is_active:
            raise AuthenticationFailed('公司已停用，请联系管理员', code='tenant_inactive')
        return user
```

- Raises DRF's `AuthenticationFailed` which the global exception handler
  converts to the standard error envelope with HTTP 401.
- The `code='tenant_inactive'` kwarg becomes the `default_code` on the exception
  (visible in DRF's `response.data['detail']` if detail dicts are used, but
  the global handler collapses it to a message string).

## Rules and Conventions

1. **Business views must NOT catch + `Response({})` manually.**
   Propagate exceptions to the global handler so the envelope format stays
   consistent. The only exceptions are:
   - `app_updates` views (deliberately uses a different shape).
   - Device-runtime views that catch `RuntimeDeviceError` and return it as
     `_error_response()`.
   - Bulk upload in `resources.views.bulk` which catches `DuplicateImageError`
     to accumulate a list of duplicates rather than failing the whole batch.

2. **Custom exceptions should inherit DRF `APIException`** for automatic
   envelope wrapping. This provides `status_code`, `default_code`, and
   the detail dict that DRF's handler consumes.

3. **Set `self.response_data` to inject extra context.**
   The global exception handler checks for `response_data` on the exception
   object and merges it into `envelope.data` when present. `DuplicateImageError`
   uses this to return the existing resource's details.

4. **Use meaningful `default_code` / `code` values** for programmatic consumers.
   Business-error codes are uppercase snake_case: `duplicate_image`,
   `tenant_inactive`, `INVALID_REQUEST`, `UPDATE_SIGNING_UNAVAILABLE`.

5. **Device-facing endpoints pre-date the envelope convention.**
   `DeviceRuntimeView`-derived views return success responses with
   `requestId`/`traceId` from the request middleware rather than the standard
   success envelope. This is legacy and should not be replicated in new code.

## `app_updates` Error Convention (Legacy)

The `apps.app_updates` module uses its own error helpers defined in `views.py`:

```python
def _trace_payload(request, **payload):
    return {'requestId': get_request_id(request), 'traceId': get_trace_id(request), **payload}

def _error_response(request, *, code: str, message: str, http_status: int, details=None):
    payload = _trace_payload(request, code=code, message=message)
    if details is not None:
        payload['details'] = details
    return Response(payload, status=http_status)
```

- No `status`/`message`/`data` envelope wrapper.
- Business `code` is always a string (`INVALID_REQUEST`, `NO_RELEASE`,
  `INVALID_THRESHOLD`, `UPDATE_SIGNING_UNAVAILABLE`).
- For serializer validation, `details=serializer.errors` passes field-level
  errors through.
- This is a legacy pattern. New subsystems should use the global DRF envelope.

## Streaming SSE generators

`StreamingHttpResponse` async generators run in Django's async context. Any synchronous helper that can evaluate an ORM queryset must run before the generator is created, or be called through `sync_to_async(..., thread_sensitive=True)`.

This matters for `POST /api/v1/ai-models/chat/conversations/{id}/send/`: `serialize_reply_blocks()` resolves referenced `Resource` rows. Calling it directly inside an async annotation SSE generator raises `SynchronousOnlyOperation` after the `200` response starts; ASGI closes the chunked stream and browsers surface the failure as `TypeError: network error`.

```python
# Wrong: the ORM query executes while the stream is iterated asynchronously.
async def annotation_event_stream():
    yield json.dumps({'blocks': serialize_reply_blocks(answer_blocks, tenant=tenant)})

# Correct: serialize in the synchronous view path, then yield only prepared data.
serialized_blocks = serialize_reply_blocks(answer_blocks, tenant=tenant, request=request)

async def annotation_event_stream():
    yield json.dumps({'blocks': serialized_blocks})
```

Regression tests that cover an async SSE generator must include a reply block with a tenant-scoped image or video resource, drain `response.streaming_content` asynchronously, and assert both the serialized media block and terminal `data: [DONE]` event. Text-only blocks do not evaluate the resource query and cannot catch this failure.

## WS / WebSocket Error Handling (Non-DRF)

WebSocket consumers in `apps/devices/realtime.py`, `apps/ai_models/realtime_asr.py`,
and `apps/ai_models/realtime_tts.py` perform JWT validation inline by
instantiating `TenantAwareJWTAuthentication()` directly and catching exceptions:

```python
authentication = TenantAwareJWTAuthentication()
validated_token = authentication.get_validated_token(token)
user = authentication.get_user(validated_token)
```

Errors in WebSocket auth close the connection — they do not return JSON error
envelopes. The DRF envelope convention applies only to HTTP API views.

## Scenario: Unified realtime error catalogue

### 1. Scope / Trigger
- Trigger: `/ws/realtime/` errors, device-runtime failures, the read-only error-code API, and the platform error-code centre share one static catalogue in `apps.error_codes.catalogue`.
- The catalogue is code-maintained only: do not create a model, migration, or write endpoint for these definitions.

### 2. Signatures
```python
from apps.error_codes.catalogue import require_error_definition_by_key

definition = require_error_definition_by_key('ASR_UPSTREAM_ERROR')
# definition.code == '1022'
```

```json
{
  "type": "asr.error",
  "id": "command-id",
  "requestId": "request-id",
  "traceId": "trace-id",
  "error": {"code": "1022", "message": "ASR 上游服务暂不可用"}
}
```

### 3. Contracts
- Every public catalogue code is a unique decimal string in the inclusive range `1001`–`2000`. Internal symbolic `key` values are backend-only lookup identifiers.
- `GET /api/v1/error-codes/` and `GET /api/v1/error-codes/{code}/` are read-only, superuser-only catalogue views. Their `code` field and lookup are the public numeric string; their `category` field is the canonical Chinese label.
- WebSocket `error`, `agent.error`, `llm.error`, `asr.error`, and `tts.error` events carry only nested `error.code` and `error.message` for the canonical error. Preserve available `id`, `requestId`, and `traceId`; never dual-write top-level `code`, `statusCode`, or `message`.
- `RuntimeDeviceError.as_payload()` retains its HTTP compatibility shape: `code` is canonical numeric, `statusCode` remains the legacy `440xx` business status, and `message` is the canonical message.
- Log underlying/upstream exception detail server-side; send a safe catalogue definition to clients.

### 4. Validation & Error Matrix
| Condition | Catalogue key | Client result |
| --- | --- | --- |
| Realtime command omits `type` | `REALTIME_COMMAND_TYPE_REQUIRED` | nested `error.code: "1013"` |
| Device authorization is expired | `DEVICE_EXPIRED` | numeric code plus HTTP `statusCode: 44014` when returned by device runtime |
| ASR upstream stream fails after start | `ASR_UPSTREAM_ERROR` | `asr.error` with safe nested numeric code; no upstream exception text |
| No catalogue definition matches | `INTERNAL_ERROR` | safe nested numeric code and message |

### 5. Good/Base/Bad Cases
- Good: backend selects a definition by symbolic key and serializes its numeric public code; UI renders API category labels directly.
- Base: a superuser filters the catalogue by an API-provided Chinese category and retrieves all matching entries.
- Bad: emitting `ASR_UPSTREAM_ERROR` as a public code, exposing `str(exc)`, or adding `legacyStatusCode` to the error-code centre.

### 6. Tests Required
- Catalogue API tests must assert superuser-only access, numeric detail lookup, filtering by Chinese category, and every code's uniqueness/range.
- WebSocket regression tests must assert nested errors, numeric `error.code`, preserved correlation fields, and absence of legacy top-level error fields.
- Device-runtime tests must assert numeric `code` while retaining the existing `statusCode` value.
- Frontend changes require `docker compose exec web npm run build`.

### 7. Wrong vs Correct
#### Wrong
```python
_send_realtime_error(send, 'asr.error', command_id, str(exc))
```

#### Correct
```python
logger.exception('realtime.asr.stream_failed')
await _send_realtime_error(
    send,
    'asr.error',
    command_id,
    require_error_definition_by_key('ASR_UPSTREAM_ERROR'),
)
```
