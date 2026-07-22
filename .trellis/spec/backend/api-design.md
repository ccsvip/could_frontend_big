# API Design Guidelines

> REST API conventions for this project.

---

## Overview

All HTTP APIs follow REST conventions under `/api/v1/`. Resources are plural nouns; actions are expressed via HTTP methods, not verb URLs.

---

## URL Conventions

| Convention | Standard |
|------------|----------|
| **Prefix** | `/api/v1/` |
| **Resource naming** | Plural kebab-case (e.g., `device-groups/`, `knowledge-bases/`, `wake-words/`) |
| **Trailing slash** | Required |
| **URL case** | kebab-case throughout — no camelCase or snake_case in path segments |
| **Lookup field** | `pk` (integer ID) by default |

### Lookup exceptions

| ViewSet | Lookup field | Reason |
|---------|-------------|--------|
| `DeviceViewSet` | `code` (string) | Devices identified by stable unique code |
| `AppUpdatesViewSet` | `release_id` (string) | Releases identified by UUID-like string ID |

**Reference files:**
- `backend/config/urls.py` — root URL configuration
- `backend/apps/*/urls.py` — per-app URL routing

---

## ViewSet Pattern

### Base classes

| Class | File | Purpose |
|-------|------|---------|
| `PermissionMappedModelViewSet` | `apps/resources/views.py` | Core base: `permission_map` dict for action-based permission dispatch |
| `DevicePermissionMixin` | `apps/devices/views.py` | Device-specific: adds `CompanyDeviceWritePermission` guard |
| `TenantScopedQuerysetMixin` | `apps/tenants/mixins.py` | Auto-scopes queryset to request's tenant |

### Permission dispatch

Define a `permission_map` dict keyed by action name:

```python
permission_map = {
    'list': [CanViewDevices],
    'retrieve': [CanViewDevices],
    'create': [CanCreateDevices],
    'update': [CanUpdateDevices],
    'partial_update': [CanUpdateDevices],
    'destroy': [CanDeleteDevices],
    'bind_voice': [CanUpdateDevices],  # custom action
}
```

Fallback: `self.action` not found → `permission_map.get('list', [])`.

### Serializer dispatch

Override `get_serializer_class()` by `self.action`:

```python
def get_serializer_class(self):
    if self.action == 'retrieve':
        return DeviceDetailSerializer
    if self.action in ('create', 'update', 'partial_update'):
        return DeviceWriteSerializer
    return DeviceSerializer
```

### Custom actions

```python
@action(detail=True, methods=['post'], url_path='update-title')
def update_title(self, request, code=None):
    ...
```

| Property | Convention |
|----------|-----------|
| `detail` | `True` for single-resource, `False` for collection |
| `methods` | Standard HTTP methods as list |
| `url_path` | kebab-case |
| Method name | snake_case |

**Reference:** `backend/apps/devices/views.py`, `backend/apps/resources/views.py`

### OpenAPI documentation

```python
@extend_schema_view(
    list=extend_schema(tags=['Devices'], parameters=[...]),
    retrieve=extend_schema(tags=['Devices']),
)
class DeviceViewSet(...):
    @extend_schema(
        request=DeviceBindVoiceSerializer,
        responses={200: DeviceSerializer},
    )
    def bind_voice(self, request, code=None):
        ...
```

### Transactions

- `perform_update` / `perform_destroy`: wrap side effects with `transaction.on_commit(lambda: publish...)`
- Batch creates: `@transaction.atomic` on `perform_create`

**Reference:** `backend/apps/devices/views.py`, `backend/apps/resources/views.py`

---

## Pagination

| Property | Value |
|----------|-------|
| **Class** | `StandardPageNumberPagination` |
| **Base** | `PageNumberPagination` |
| **File** | `backend/config/pagination.py` |
| **Default page_size** | 10 |
| **Max page_size** | 100 |
| **Query params** | `page` (1-indexed), `page_size` |

### Response format

```json
{
  "count": 42,
  "next": "http://example.com/api/v1/devices/?page=3",
  "previous": "http://example.com/api/v1/devices/?page=1",
  "results": [...]
}
```

### Exception

`PointViewSet` supports `?all=true` to bypass pagination (admin-only).

---

## Query Filtering

Override `get_queryset()` and parse `request.query_params`:

```python
def get_queryset(self):
    qs = super().get_queryset()
    keyword = self.request.query_params.get('keyword')
    device_code = self.request.query_params.get('deviceCode')
    if keyword:
        qs = qs.filter(name__icontains=keyword)
    if device_code:
        qs = qs.filter(device__code=device_code)
    return qs
```

| Convention | Standard |
|------------|----------|
| **Param naming** | camelCase (e.g., `keyword`, `deviceCode`, `isActive`, `tenantId`) |
| **Filter operators** | `icontains`, `exact`, `in`, `gte`/`lte` (for dates) |

---

## Request/Response Envelope

### Success

```json
{
  "status": "success",
  "message": "操作成功",
  "data": { ... }
}
```

**Reference:** `backend/apps/accounts/views.py:130-137`

### Error (via global exception handler)

```json
{
  "status": "error",
  "message": "错误描述",
  "code": 400
}
```

**Reference:** `backend/config/exceptions.py`

All DRF exceptions pass through `config.exceptions.custom_exception_handler` which wraps them in the standard envelope. Business views must NOT return hand-crafted `Response()` objects — propagate exceptions to the global handler.

### app_updates exception

The `app_updates` app uses a custom format with business error codes:

```json
{
  "requestId": "uuid",
  "traceId": "uuid",
  "code": "INVALID_REQUEST",
  "message": "错误描述",
  "details": "..."
}
```

**Reference:** `backend/apps/app_updates/views.py`

---

## Tracing Headers

| Header | Source | Purpose |
|--------|--------|---------|
| `X-Request-ID` | `config/request_id.py` middleware | Auto-generated UUID per request |
| `X-Trace-ID` | `config/request_id.py` middleware | Cross-service tracing |

---

## Standard Action URL Patterns

| Action | HTTP | URL |
|--------|------|-----|
| List | `GET` | `/api/v1/<resources>/` |
| Retrieve | `GET` | `/api/v1/<resources>/{lookup}/` |
| Create | `POST` | `/api/v1/<resources>/` |
| Update | `PATCH` | `/api/v1/<resources>/{lookup}/` |
| Delete | `DELETE` | `/api/v1/<resources>/{lookup}/` |
| Custom (detail) | `POST` | `/api/v1/<resources>/{lookup}/<action>/` |
| Custom (collection) | `GET` | `/api/v1/<resources>/<action>/` |

---

## Forbidden Patterns

- Verb URLs (`/updateDeviceName/`, `/deleteDevice/`)
- Non-standard HTTP methods for CRUD
- camelCase or snake_case in URL path segments
- Hand-crafted `Response()` in business views (bypasses global error envelope)
- Try/except + silent failure — propagate to global handler
- Bypassing `TenantScopedQuerysetMixin` in tenant-scoped endpoints
