# Frontend State Management

Revision: 2026-07-22

## Principles

1.  **Minimal global state.** Only truly cross-page or cross-component state belongs in Zustand stores. Page-local state stays in `useState` / `useReducer`.
2.  **Server state is not global state.** There is no React Query, RTK Query, or SWR. API responses are fetched directly in components and held in local `useState`.
3.  **Side-effect feedback uses antd.** Use `message.success` / `message.error` (or `notification`) for operation feedback, not store actions.

---

## 1. Global State: Zustand

All global stores live in `web/src/store/` and are created with `create()` from `zustand` (v5). **No middleware** (no `devtools`, `persist`, `immer` — persistence is manual via `localStorage`).

### 1.1 `useAuthStore` — `web/src/store/auth.ts`

The single source of truth for authentication and authorization.

```typescript
interface AuthState {
  // --- State ---
  token: string | null;
  refreshToken: string | null;
  username: string;
  role: AppRole;                    // null | { id: number; name: string; … }
  permissions: string[];            // e.g. ['devices.view', 'tenant.management.view']
  menus: AppMenu[];                 // sidebar menu tree
  tenant: AppTenant;                // null | { tenantId: number; tenantName: string; isTenantAdmin: boolean; … }
  isSuperuser: boolean;
  mustChangePassword: boolean;
  authSyncStatus: AuthSyncStatus;   // 'idle' | 'syncing' | 'ready'

  // --- Actions ---
  login: (payload: LoginPayload) => void;
  setUserContext: (payload: UserContextPayload) => void;
  setAuthSyncStatus: (status: AuthSyncStatus) => void;
  logout: () => void;
  clearAuth: () => void;
  hasPermission: (permission: string) => boolean;
}
```

**Persistence strategy** — manual `localStorage` read/write:

- On init, the store reads token/refreshToken/username/role/permissions/menus/tenant from `localStorage`. If a token exists but `authSyncStatus` starts as `'idle'` (indicating the page needs to re-sync with the backend).
- `login()` writes all fields to `localStorage` then calls `set()`.
- `logout()` / `clearAuth()` clear `localStorage` and reset the store to defaults.
- See storage key constants at the top of the file (`TOKEN_STORAGE_KEY`, `REFRESH_TOKEN_STORAGE_KEY`, `USERNAME_STORAGE_KEY`, `ROLE_STORAGE_KEY`, `PERMISSIONS_STORAGE_KEY`, `MENUS_STORAGE_KEY`, `TENANT_STORAGE_KEY`, `IS_SUPERUSER_STORAGE_KEY`, `MUST_CHANGE_PASSWORD_STORAGE_KEY`).

**Consumption pattern** — selector functions, NOT destructuring:

```typescript
// Correct: selector returns only the needed slice → no unnecessary re-renders
const token = useAuthStore((state) => state.token);
const hasPermission = useAuthStore((state) => state.hasPermission);
const menus = useAuthStore((state) => state.menus);

// Correct: derived check without extra selector
const canViewDevices = useAuthStore((state) => state.hasPermission('devices.view'));

// Never: destructured object causes re-render on every store change
// const { token, username } = useAuthStore();  // AVOID
```

**Pseudo-actions** — methods that read state without subscribing:

- `hasPermission(permission)` uses `get()` internally via the store definition; consumers call it as a selector.

**Read-only access** — HTTP interceptor reads token/tenantScope without subscribing:

```typescript
// In web/src/api/client.ts — non-reactive read via getState()
const token = useAuthStore.getState().token;
const tenantId = useTenantScopeStore.getState().tenantId;
```

### 1.2 `useTenantScopeStore` — `web/src/store/tenant-scope.ts`

Manages the superuser's "browse as tenant" scope. Only meaningful inside `/tenants/:tenantId/*` routes.

```typescript
interface TenantScopeState {
  tenantId: number | null;
  includeHiddenTenants: boolean;
  setTenantId: (tenantId: number | null) => void;
  setIncludeHiddenTenants: (includeHiddenTenants: boolean) => void;
  clear: () => void;
}
```

**Lifecycle:**

- Written when a superuser navigates into a tenant-scoped route (e.g., via the tenant selector).
- Cleared when the user leaves tenant-scoped routes.
- The request interceptor in `client.ts` reads `useTenantScopeStore.getState().tenantId` and appends `?tenant=<id>` to scoped URLs (see `TENANT_SCOPED_PREFIXES` whitelist).

**Consumption pattern** — same selector pattern:

```typescript
const tenantScopeId = useTenantScopeStore((state) => state.tenantId);
```

---

## 2. Server State: Direct Axios Calls

### 2.1 HTTP Client — `web/src/api/client.ts`

A single axios instance (`httpClient`) configured at module level:

```typescript
export const httpClient = axios.create({
  baseURL: API_BASE_URL,   // import.meta.env.VITE_API_BASE_URL || '/api/v1'
});
```

**Interceptors:**

| Interceptor | Purpose |
|---|---|
| **Request** | Attach `Authorization: Bearer <token>` from `useAuthStore.getState().token`. Append `?tenant=<id>` for tenant-scoped requests (whitelisted paths only). |
| **Response** (success) | Pass through unchanged. |
| **Response** (error) | On 401 → call `handleUnauthorizedResponse()` which calls `useAuthStore.getState().clearAuth()` and redirects to `/login`. Other errors propagate to the caller. |

### 2.2 API Modules — `web/src/api/modules/*.ts`

Each backend resource group has a module file exporting typed async functions:

```
web/src/api/modules/
  auth.ts             # login, register, changePassword, fetchAccountApplications, …
  devices.ts          # fetchDevices, updateDevice, deleteDevice, …
  tenants.ts          # fetchTenants, createTenant, …
  resources.ts        # fetchResources, uploadResource, …
  commands.ts         # fetchControlCommands, createTaskCommand, …
  applications.ts     # fetchAgentApplications, createAgentApplication, …
  chat.ts             # sendChatMessage, fetchChatHistory, …
  …
```

**Signature convention** — every function:

- Returns the axios response `data` directly (the interceptor already unwraps errors).
- Accepts query params or payload objects as arguments.
- Uses `httpClient` (not a raw axios instance).

```typescript
// Typical API module function
export const fetchDevices = async (query?: DeviceListQuery): Promise<DeviceListResponse> => {
  const { data } = await httpClient.get('/devices/', { params: query });
  return data;
};
```

### 2.3 Component Data Fetching Pattern

All server-state data lives in component-local `useState`. The pattern is consistent across every view:

```typescript
export const MyPage = () => {
  const [data, setData] = useState<DataType[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchData();
      setData(result);
    } catch {
      // Error already handled by axios response interceptor (401 redirect)
      // or caught here for local error feedback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // For mutations, use event handlers with try/catch and antd feedback:
  const handleSave = async () => {
    // in-progress state is local
    try {
      await updateResource(id, payload);
      message.success('保存成功');
      void loadData();    // reload the list
    } catch {
      message.error('保存失败');
    }
  };

  return (
    <Spin spinning={loading}>
      {/* render data */}
    </Spin>
  );
};
```

**Key rules:**

- `useState` + `useEffect` is the only data-fetching pattern. No `useReducer` for server data.
- `useCallback` wraps the load function so it can be safely listed in `useEffect` deps.
- `void` prefix on the async call inside `useEffect` (no floating-promise lint warnings).
- Loading state drives `<Spin>` or `<Table loading={…}>`.

### 2.4 Error Handling in Components

| Location | Strategy |
|---|---|
| **Response interceptor** (401) | Clears auth, redirects to `/login` — no component code needed. |
| **Mutation handlers** | `try / catch` with `message.error()` for user-visible feedback. |
| **Load effects** | `try / catch` with optional `message.error()`; some views suppress the error because the interceptor already handles it. |

---

## 3. Routing State: react-router-dom v6

### 3.1 URL as State Source

URL search params serve as a lightweight, shareable state source for filter/page values:

```typescript
const [searchParams, setSearchParams] = useSearchParams();

// Read
const titleFilter = searchParams.get('title')?.trim() || '';

// Write (merges with existing params)
setSearchParams((prev) => ({ ...Object.fromEntries(prev), title: newValue }));
```

### 3.2 Route Guards

Route-level authorization is enforced via wrapper components in `web/src/router/index.tsx`:

| Guard | Condition | Redirect target |
|---|---|---|
| `PermissionGuard` | User has `permission` string (or no permission required) | First accessible path from user's menu tree |
| `SuperuserGuard` | `isSuperuser === true` | First accessible path |
| `AuditLogGuard` | Has `audit.logs.view` AND (`isSuperuser` OR `tenant.isTenantAdmin`) | First accessible path |

All guards check `authSyncStatus` first and render `<AuthSyncFallback />` while auth is initializing.

```typescript
<Route element={<PermissionGuard permission="devices.view" />}>
  <Route path="devices" element={<DeviceManagementPage />} />
</Route>
```

### 3.3 Navigation and Location

- `useNavigate()` for imperative navigation.
- `useLocation()` for reading `pathname` / `state` (e.g., to determine active route in a mixed view).
- `useParams()` for dynamic route segments (`/tenants/:tenantId/devices`).

---

## 4. Form State: Ant Design `Form.useForm()`

Form state is managed by Ant Design's form instance, not raw `useState`.

```typescript
const [form] = Form.useForm<FormValues>();

// Initial values via <Form initialValues={…} />
// Values read on submit via form.validateFields() or form.getFieldsValue()
// Programmatic set via form.setFieldsValue({ … })
```

Exception: When form fields need to drive conditional rendering outside the `<Form>` (e.g., disabling a button based on a field value), mirror the relevant field(s) in `useState` and sync via `onValuesChange`.

```typescript
const [runtimeBackendType, setRuntimeBackendType] = useState<RuntimeBackendType>('platform_llm');

<Form onValuesChange={(changed) => {
  if ('runtimeBackendType' in changed) setRuntimeBackendType(changed.runtimeBackendType);
}}>
```

---

## 5. UI State Categories

### 5.1 Modal/Drawer Visibility

```typescript
const [formVisible, setFormVisible] = useState(false);
const [editingItem, setEditingItem] = useState<Record | null>(null);
```

- `editingItem !== null` doubles as "edit mode" vs "create mode".
- Close handler: `setFormVisible(false); setEditingItem(null);`

### 5.2 Loading / Saving Flags

Each asynchronous operation has its own boolean:

```typescript
const [loading, setLoading] = useState(false);           // initial data load
const [saving, setSaving] = useState(false);             // form submission
const [actionLoading, setActionLoading] = useState<number | null>(null);  // per-row action (stores the row id)
```

Per-row loading uses the record's `id` as the indicator:

```typescript
const [uploadingReleaseId, setUploadingReleaseId] = useState<string | null>(null);

<Button loading={uploadingReleaseId === record.id}
        onClick={() => handleUpload(record.id)} />
```

### 5.3 Pagination / Search State

```typescript
const [page, setPage] = useState(1);
const [pageSize] = useState(10);                        // stable — no setter needed
const [total, setTotal] = useState(0);
const [keyword, setKeyword] = useState('');             // applied value
const [keywordInput, setKeywordInput] = useState('');   // unapplied input (Search on Enter)
```

Two-value keyword pattern allows the input field to hold a draft while the actual query fires only on Enter or debounce:

```typescript
const query = useMemo<DeviceListQuery>(() => ({ page, keyword }), [page, keyword]);

<Input.Search
  value={keywordInput}
  onChange={(e) => setKeywordInput(e.target.value)}
  onSearch={(value) => { setKeyword(value); setPage(1); }}
/>
```

---

## 6. WebSocket / Real-Time State

WebSocket connections are managed entirely within components or custom hooks using `useRef` and `useState` — **never in Zustand**.

```typescript
const socketRef = useRef<WebSocket | null>(null);
const [connected, setConnected] = useState(false);

// Lifecycle managed in useEffect return (cleanup)
useEffect(() => {
  socketRef.current = new WebSocket(url);
  return () => {
    socketRef.current?.close();
  };
}, [url]);
```

The real-time API utilities in `web/src/api/realtime.ts` provide helpers for building URLs, encoding commands, and constructing typed payloads. They do **not** manage connection state.

---

## 7. Derived / Computed Values

Use `useMemo` for derived data, not store selectors or helper functions called in render:

```typescript
const filteredData = useMemo(
  () => data.filter((item) => item.status === statusFilter),
  [data, statusFilter],
);

const columns = useMemo<ColumnsType<Record>>(
  () => [
    // column definitions
  ],
  [/* dependencies that affect columns */],
);
```

---

## 8. Anti-Patterns

| ❌ Don't | ✅ Do |
|---|---|
| Put page-local loading/form/modal state in Zustand | Keep it in `useState` |
| Destructure the entire Zustand store (`const { token, username } = useAuthStore()`) | Use individual selectors |
| Call `axios.get` directly in a component | Define the call in `api/modules/*.ts` |
| Use `useState` for every form field (name, description, …) | Use `Form.useForm()` with `onValuesChange` for derived state |
| Use a single `loading` boolean for unrelated async operations | Use separate flags per operation |
| Poll the store with `.getState()` inside a React component (misses updates) | Use selector hooks |
| Store server data in Zustand for caching | Re-fetch on mount with `useEffect` |
| Manage WebSocket lifecycle in Zustand | Keep in `useRef` / component state |
