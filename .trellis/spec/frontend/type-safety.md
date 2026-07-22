# Type Safety

> TypeScript type safety conventions for the could_frontend project.

---

## Overview

- **Type system:** TypeScript 5.x with strict mode (`tsc -b`, `strict: true`).
- **No runtime validation:** No Zod, Yup, io-ts, or similar libraries. All type enforcement happens at compile time only.
- **No OpenAPI codegen:** drf-spectacular generates the backend OpenAPI schema, but frontend types are written by hand. No automated type generation from API contracts.
- **Type definitions use `type` exclusively:** The codebase uses `export type` for all shape definitions — API responses, payloads, query parameters, store state, and utility types. `interface` is not used for data shapes.

---

## Type Definition Locations

| Location | Purpose | Examples |
|---|---|---|
| `web/src/api/modules/*.ts` | **Primary** — request/response types co-located with API functions | `DeviceRecord`, `LoginResponse`, `CommandGroupPayload`, `PaginatedResponse<T>` |
| `web/src/views/<page>/types.ts` | View-specific form/UI types | `BindForm`, `BindMode`, `SelectOption<T>` |
| `web/src/store/auth.ts` | Store state types (inline with Zustand store) | `AuthState`, `LoginPayload`, `AppRole`, `AppMenu` |
| `web/src/store/tenant-scope.ts` | Store state types (inline, no separate type file) | `TenantScopeState` (private) |
| `web/src/vite-env.d.ts` | Global ambient module augmentation | `@tabler/icons-react` icon exports |
| **No shared global types file** | — | Types are per-module |

### Module type categories within `api/modules/*.ts`

Each API module file defines several categories of types:

```
web/src/api/modules/
├── devices.ts      # DeviceRecord, DeviceListQuery, DeviceUpdatePayload, PaginatedResponse<T>
├── auth.ts         # LoginPayload, CurrentUser, LoginResponse, AccountApplicationRecord
├── commands.ts     # CommandGroupRecord, ControlCommandPayload, PaginatedResponse<T>
├── applications.ts # AgentApplicationRecord, AgentReplyBlock, AgentAnnotationRecord
├── knowledge-base.ts # KnowledgeBaseRecord, KnowledgeDocumentRecord, KnowledgeModelSettings
├── resources.ts    # ResourceRecord, DuplicateImageLocation, VideoPresignResponse
├── tenants.ts      # TenantRecord, MenuCatalogItem, MenuCatalogResponse
├── employees.ts    # EmployeeRecord, TenantRoleRecord
├── llm-settings.ts # PlatformLLMProviderRecord, TenantLLMAuthorization
├── chat.ts         # ChatMessage, ChatConversationDetail
├── ... (19 modules total)
```

---

## Type Naming Conventions

The codebase follows consistent naming patterns:

| Suffix / Pattern | When to Use | Example |
|---|---|---|
| `*Record` | Entity returned by the backend (read / list responses) | `DeviceRecord`, `AgentApplicationRecord`, `TenantRecord` |
| `*Payload` | Payload sent to create or update an entity | `DeviceUpdatePayload`, `CommandGroupPayload`, `TenantMenuSelection` |
| `*ListResponse` | Paginated list response (includes `count`, `next`, `previous`, `results`) | `DeviceListResponse`, `OperationLogListResponse` |
| `*Query` / `*ListQuery` | Query parameters for list endpoints | `DeviceListQuery`, `CommandGroupListQuery`, `KnowledgeBaseListQuery` |
| `*Response` | Non-paginated detail / action response | `DeviceStatsResponse`, `BatchImageResourceResponse`, `LoginResponse` |
| Plain name | Simple types, unions, enums, utility types | `DeviceStatus`, `ResourceType`, `ControlCommandReplyStrategy`, `BindMode` |

### Record vs Payload distinction

- **`*Record`** mirrors the backend serializer output — all fields returned by the API, including read-only fields (`id`, `created_at`, `updated_at`, computed properties).
- **`*Payload`** represents only the writable fields sent in POST/PATCH/PUT requests. Optional fields use `?` or `| undefined`.

```typescript
// Read model (returned by API)
export type ApplicationRecord = {
  id: number;
  name: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  isActive: boolean;
};

// Write model (sent to API for create/update)
export type ApplicationPayload = {
  name: string;
  description?: string;
  isActive?: boolean;
};
```

### Union types for constrained string fields

String enum fields use `type` union aliases, not `enum`:

```typescript
export type DeviceStatus = 'online' | 'offline';
export type DeviceAuthorizationType = 'permanent' | 'trial';
export type ControlCommandReplyStrategy = 'fixed' | 'generated';
export type ResourceCategory = 'horizontal' | 'vertical' | 'uncategorized';
export type AuthSyncStatus = 'idle' | 'syncing' | 'ready';
```

---

## API Type Architecture

### httpClient generic typing

The Axios instance (`httpClient`) is called with a generic type parameter that types the entire response data:

```typescript
const response = await httpClient.get<DeviceRecord>(`/devices/${code}/`);
return response.data; // typeof DeviceRecord
```

All HTTP methods (`get`, `post`, `patch`, `put`, `delete`) accept a type parameter:

```typescript
httpClient.get<DeviceListResponse>(url, { params });
httpClient.post<DeviceRecord>(url, payload);
httpClient.patch<DeviceRecord>(url, payload);
httpClient.put<TenantKnowledgeAuthorization>(url, payload);
httpClient.delete<BulkImageResourceDeleteResponse>(url, { data });
```

### PaginatedResponse pattern

`PaginatedResponse<T>` is duplicated in each module that needs it, not shared globally. Two slightly different forms exist:

```typescript
// commands.ts
export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

// devices.ts (same shape)
export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
```

Some endpoints may return either a paginated response or a flat array. The `normalizeList` helper handles this:

```typescript
const normalizeList = <T>(value: PaginatedResponse<T> | T[]): PaginatedResponse<T> => {
  if (Array.isArray(value)) {
    return { count: value.length, next: null, previous: null, results: value };
  }
  return value;
};
```

**Recommendation:** Extract `PaginatedResponse<T>` to a shared location (e.g., `web/src/api/types.ts`) to avoid duplication across modules.

### ApiResponse wrapper

Some endpoints wrap responses in a standard envelope:

```typescript
// client.ts
export type ApiResponse<T = unknown> = {
  status: 'success' | 'error';
  message: string;
  data?: T;
};
```

This is used directly in API function calls where the backend returns the envelope:

```typescript
const response = await httpClient.post<ApiResponse>('/auth/change-password/', payload);
const response = await httpClient.post<ApiResponse<AccountApplicationRecord>>('/auth/account-applications/', payload);
```

---

## Type Composition Patterns

### Partial for partial updates

Update functions use `Partial<PayloadType>` for the payload:

```typescript
export const updateDevice = async (deviceCode: string, payload: DeviceUpdatePayload) => { ... };
// vs inline Partial:
export const updatePoint = async (id: number, payload: Partial<PointPayload>) => { ... };
```

### Omit + intersection

```typescript
// Remove a field and add a differently-typed replacement
export type AsrStatusRecord = Omit<AsrSettingsRecord, 'apiKey'>;

// Extend a base type with additional fields
export type DeviceAuthorizationRequestRecord = DeviceRecord & {
  bindingStatus: 'pending' | 'bound' | 'ignored';
  runtimeStatus: 'waiting_application' | 'waiting_agent' | 'ready';
};

// Override specific fields from a base type
export type DeviceChatSessionMessage = Omit<ChatMessage, 'created_at'> & {
  createdAt: string;
  commandDispatch: ControlCommandDispatchDiagnostics;
};
```

### Discriminated unions

```typescript
export type AgentReplyBlock =
  | { type: 'text'; text: string }
  | { type: 'image' | 'video'; resourceId: number; resourceName: string; url: string; missing?: boolean };
```

### Record<string, unknown> for dynamic shapes

```typescript
// Dynamic metadata / device info blocks
latestActivationDeviceInfo: Record<string, unknown>;
content: Record<string, unknown>;
headers: Record<string, string>;
```

---

## Forbidden and Discouraged Patterns

| Pattern | Status | Alternative |
|---|---|---|
| `any` | **Forbidden** | Use `unknown` with type narrowing, or define a proper type |
| `as` type assertions | **Discouraged** | Prefer proper type annotations or type guards |
| `interface` for data shapes | **Not used** | Use `type` (project convention) |
| Runtime validation libraries (Zod, Yup) | **Not installed** | Not needed — compile-time checking only |

### Exception for `as`

A small number of `as` casts exist in the codebase (e.g., `resources.ts:259`). These are limited to cases where TypeScript cannot infer a union discriminant from external API contract guarantees. New code should avoid `as`; use type guards or restructure the types instead.

---

## TypeScript Configuration

- **Strict mode** enabled (`strict: true` in `tsconfig.json`).
- **`tsc -b`** is the build command — no `skipLibCheck` bypassing for production code.
- The project does not use `paths` aliases — all imports are relative.

---

## Known Gaps and Future Improvements

1. **No OpenAPI type generation** — Frontend types are handwritten and must be manually kept in sync with the backend DRF serializers. Consider adding `openapi-typescript` or a similar codegen pipeline.

2. **Duplicated `PaginatedResponse<T>`** — Defined independently in `commands.ts` and `devices.ts` with identical shape. Should be extracted to a shared module.

3. **No type guards** — The codebase has zero user-defined type guard functions (`isX(value): value is X`). When dealing with `unknown` or union types, add explicit type guards.

4. **No shared types barrel** — There is no `web/src/types/` or `web/src/api/types.ts` barrel for commonly-used generic types. Consider consolidating shared generics.

5. **Inconsistent boolean field naming** — Most booleans use `is*` prefix (`isActive`, `isEnabled`, `isVisible`, `isSoftwareTrial`) but some use bare adjectives (`configured`, `visible`, `enabled`). Standardize on `is*` prefix for all boolean fields.

---

## Enforcement

- TypeScript strict mode catches most type errors at build time.
- Run `tsc -b` to type-check the entire project.
- No additional lint rules beyond TypeScript's built-in strict checks.
