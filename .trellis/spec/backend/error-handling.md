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
