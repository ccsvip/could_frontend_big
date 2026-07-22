# Security Guidelines

> Authentication, authorization, tenant isolation, and secure coding practices.

---

## Authentication

### JWT Authentication

| Property | Value |
|----------|-------|
| **Library** | `rest_framework_simplejwt` |
| **Custom class** | `TenantAwareJWTAuthentication` (`apps/accounts/authentication.py`) |
| **Extends** | simplejwt with tenant-active check |

Custom behavior:
- Extends `simplejwt` with tenant status verification
- Raises `AuthenticationFailed('公司已停用，请联系管理员', code='tenant_inactive')` when tenant is disabled

### Token Lifetimes

| Token | Default lifetime | Env override |
|-------|-----------------|-------------|
| **Access token** | 30 minutes | `JWT_ACCESS_MINUTES` |
| **Refresh token** | 7 days | `JWT_REFRESH_DAYS` |

### Auth Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/login/` | POST | Login |
| `/api/v1/auth/refresh/` | POST | Refresh access token |
| `/api/v1/auth/me/` | GET | Current user info |

### Device-Code Authentication

For Android/device runtime endpoints, the `X-Device-Code` header bypasses JWT:

```
X-Device-Code: <device_code>
```

| Extraction context | Method |
|-------------------|--------|
| REST views | `request.headers.get('X-Device-Code')` |
| WebSocket ASR | headers → query params (case-insensitive bytes) |
| WebSocket TTS | query params only |
| Device activation | headers → `request.data` |

Device validation:
```python
from apps.devices.services.runtime import get_runtime_device
device = get_runtime_device(device_code, require_tenant=False, allow_expired=False)
```

**Rule:** Device-code auth is for **read-only runtime endpoints only**. Management APIs must use JWT.

### Business Error Codes for Device Auth

| Code | statusCode | Meaning |
|------|-----------|---------|
| `DEVICE_CODE_REQUIRED` | 44001 | Missing device code |
| `DEVICE_NOT_REGISTERED` | 44004 | Device not found |
| `DEVICE_CODE_DUPLICATED` | 44009 | Duplicate device code |
| `DEVICE_TENANT_UNBOUND` | 44011 | Device not bound to tenant |
| `DEVICE_TENANT_DISABLED` | 44012 | Device's tenant is disabled |
| `DEVICE_DISABLED` | 44013 | Device is disabled |
| `DEVICE_EXPIRED` | 44014 | Device authorization expired |
| `DEVICE_AGENT_UNBOUND` | 44021 | Device not bound to agent |
| `DEVICE_APPLICATION_INACTIVE` | 44022 | Device application inactive |

**Reference:** `backend/apps/devices/services/runtime.py`

---

## Authorization (Permission Hierarchy)

All permission classes live in `backend/apps/accounts/permissions.py`.

```
BasePermission
├── IsAdminRole                    # is_staff or is_superuser
├── IsSuperUser                    # only is_superuser — platform-level ops
├── IsAuthenticatedReadOnlyOrAdminWrite  # safe=authenticated, write=admin
├── CompanyDeviceWritePermission   # write operations require company tenant
└── HasPermissionCode (abstract)
      ├── CanViewDevices, CanCreateDevices, CanUpdateDevices, CanDeleteDevices
      ├── CanViewImageResources, CanCreateImageResources, ...
      ├── CanManageTenants, CanManageEmployees
      ├── CanViewAuditLogs, CanClearAuditLogs
      ├── CanViewCompanyLLMOptions, CanViewCompanyTTSOptions (compound)
      └── ~50+ concrete classes
```

### Permission Code Format

`{domain}.{action}` — e.g., `devices.view`, `resources.images.create`, `audit.logs.view`

### Permission Resolution Logic

`accounts/services/permissions.py::get_active_permission_codes_for_user()`:

| User type | Permission set |
|-----------|---------------|
| **Superuser** | All `PermissionPoint` records |
| **Tenant admin** | Tenant grants + inherent permissions (employee management, audit) |
| **Regular employee** | Tenant grants only |

### Permission Dispatch in ViewSets

Use `permission_map` dict pattern:

```python
class MyViewSet(PermissionMappedModelViewSet):
    permission_map = {
        'list': [CanViewResource],
        'create': [CanCreateResource],
        ...
    }
```

**Reference:** `backend/apps/resources/views.py` (PermissionMappedModelViewSet)

---

## Tenant Isolation

### Mechanism

| Component | Purpose |
|-----------|---------|
| `TenantScopedQuerysetMixin` | Auto-filters queryset by request's tenant |
| `TenantManager` (model manager) | Default manager for tenant-scoped models |

### Behavior

| User type | Queryset scope |
|-----------|---------------|
| **Regular user** | Own tenant's data only |
| **Superuser** | All tenants (filterable via `?tenantId=` query param) |
| **Unaffiliated user** | Empty queryset |

### Rules

- All models with a `tenant` FK must use `TenantManager`
- Views for tenant-scoped resources must include `TenantScopedQuerysetMixin`
- Never accept `tenant_id` from request body — derive from authenticated user or superuser's `?tenantId=`
- Superuser `?tenantId=` must be validated against existing tenant

---

## Input Validation

| Layer | Mechanism |
|-------|-----------|
| **Serializer** | DRF field validators + `validate_<field>()` methods |
| **View** | `ParseError` for malformed requests |
| **Service** | Explicit parameter validation before processing |

**Rule:** Validate once at the entry point. Don't scatter validation across layers.

---

## Secrets Management

- Never hardcode secrets, API keys, or credentials in source code
- Load from environment variables via Django settings
- Third-party API keys stored in database via encrypted fields (`apps/ai_models/credential_crypto.py`)

**Rule:** If it's sensitive, it belongs in an env variable or encrypted DB field, not in code.

---

## Rate Limiting

DRF Throttling classes available. Usage varies by endpoint — check individual ViewSets.

---

## Audit Logging

| Component | Location | Purpose |
|-----------|----------|---------|
| **Audit app** | `apps/audit/` | Operation log tracking |
| **Middleware** | `apps/audit/middleware.py` | Automatic request logging |
| **Permissions** | `CanViewAuditLogs`, `CanClearAuditLogs` | Audit log access control |

---

## CORS

Configured in Django settings per environment (allowed origins vary between dev and prod).

---

## Forbidden Patterns

- Platform-level API using `IsAdminUser` (checks `is_staff`) — use `IsSuperUser` instead
- Accepting `tenant_id` from mutable request body in tenant-scoped views
- Hardcoding API keys or secrets
- Bypassing permission checks in serializers or services
- Device-code auth on management or write APIs
- `try/except` + silent failure that swallows security exceptions
