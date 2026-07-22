# Frontend Directory Structure

> Project: could_frontend (`web/` directory)
> Stack: React 18 + TypeScript + Vite, Ant Design 5, Tailwind CSS, Zustand 5, react-router-dom v6
> Last updated: 2026-07-22

## Top-Level Layout

```
web/
├── index.html                  # Vite HTML entry point
├── package.json                # Dependencies & scripts
├── tsconfig.json               # TypeScript strict config (tsc -b)
├── vite.config.ts              # Vite build config
├── tailwind.config.ts          # Tailwind theme: brand-* palette (#0f766e), container, shadows
├── postcss.config.js           # PostCSS for Tailwind (autoprefixer)
├── public/                     # Static assets served as-is
├── scripts/                    # Standalone test/simulation scripts (.mjs)
├── src/
│   ├── main.tsx                # App entry: ReactDOM root, ConfigProvider (antd theme + zhCN locale)
│   ├── vite-env.d.ts           # Global type augmentations (@tabler/icons-react module defs)
│   ├── assets/                 # Static imports (images, SVGs used in components)
│   ├── styles/
│   │   └── index.css           # Global CSS: Tailwind directives, antd overrides, fluid typography,
│   │                           #   page-hero, chat-markdown, custom-scrollbar, sidebar menu colors
│   ├── api/                    # HTTP & WebSocket layer
│   │   ├── client.ts           # Axios singleton (httpClient), API_BASE_URL, interceptors (auth token,
│   │   │                       #   tenant-scope param, 401 redirect), media URL normalizer
│   │   ├── realtime.ts         # WebSocket URL builder, command/response envelope builders & parser
│   │   └── modules/            # One file per backend resource — data types + fetch functions
│   ├── router/
│   │   └── index.tsx           # react-router-dom v6 route tree, lazy-loaded views, AuthGuard,
│   │                           #   PermissionGuard, TenantScopeOutlet, GuestGuard
│   ├── store/                  # Zustand v5 stores
│   │   ├── auth.ts             # Auth state: token, user context, permissions, menus, tenant, persistence
│   │   └── tenant-scope.ts     # Super-admin tenant browsing scope (tenantId + includeHiddenTenants)
│   ├── components/             # Shared/reusable UI components
│   ├── layouts/                # Layout components (one layout file)
│   │   └── dashboard-layout.tsx # DashboardLayout: sidebar (Menu), header, nested <Outlet />
│   └── views/                  # Page-level view components, each a named export used by router
│       ├── login/              # LoginPage
│       ├── force-password-change/
│       ├── device-management/
│       ├── device-authorization-center/
│       ├── application-management/
│       ├── command-management/  # Multi-page: workspace, points, export, tasks, groups + sub-components
│       ├── knowledge-base/
│       ├── knowledge-base-settings/
│       ├── asr-management/
│       ├── asr-settings/
│       ├── tts-management/
│       ├── tts-settings/
│       ├── llm-management/     # Re-exports LlmSettingsPage from llm-settings as LlmManagementPage
│       ├── llm-settings/
│       ├── settings-llm/
│       ├── model-management/
│       ├── resource-management/
│       ├── scrolling-text-management/
│       ├── app-update-management/
│       ├── tenant-management/
│       ├── employee-management/
│       ├── account-applications/
│       ├── log-management/
│       ├── minio-settings/
│       ├── third-party-chatbot-settings/
│       └── media-devices.ts    # (standalone flat file)
```

## Directory Responsibilities

### `src/api/` — HTTP & WebSocket Layer

| Path | Purpose |
|------|---------|
| `client.ts` | Exports `httpClient` (axios instance), `API_BASE_URL`, `ApiResponse<T>`, `normalizeMediaAssetUrl()`, `handleUnauthorizedResponse()`. Request interceptor injects auth token + tenant-scope param. Response interceptor handles 401 (clear auth + redirect) and normalizes media URLs. |
| `realtime.ts` | WebSocket URL builder (`buildRealtimeWebSocketUrl`), typed command/response envelope helpers, command factory functions for ASR/TTS/LLM/device-events. |
| `modules/*.ts` | One kebab-case file per backend resource. Each module exports TypeScript types (interfaces/type aliases for API payloads and responses) and async `fetch*`/`create*`/`update*`/`delete*` functions that call `httpClient`. |

#### API Modules (20 files)

```
api/modules/
├── app-updates.ts       # App releases, OTA update
├── applications.ts      # Agent applications
├── asr.ts               # ASR settings
├── audit.ts             # Operation audit logs
├── auth.ts              # Login/logout, token refresh, menus, permissions
├── chat.ts              # Chat messages & conversations
├── commands.ts          # Control commands, command groups
├── devices.ts           # Device CRUD, groups, applications, wake-words, chat logs/sessions, authorizations
├── employees.ts         # Employee management
├── knowledge-base.ts    # Documents, uploads, vector recall
├── llm-providers.ts     # LLM provider config & test connection
├── llm-settings.ts      # LLM model options & settings
├── models.ts            # 3D model assets
├── point-management.ts  # Command points (script step)
├── resources.ts         # Media resources (image/video upload, categories)
├── scrolling-texts.ts   # Scrolling text display config
├── settings.ts          # Minio storage settings
├── tenants.ts           # Tenant CRUD, menu catalog
├── tts.ts               # TTS voice management
└── voice-tones.ts       # Voice tones
```

**Rule:** Every new backend resource gets one file here, named in kebab-case matching the backend URL prefix. All data types for that resource are co-located in the same file (not a separate `types.ts`).

### `src/store/` — Zustand State

| File | Store | Purpose |
|------|-------|---------|
| `auth.ts` | `useAuthStore` | Token persistence (localStorage), user context (username, role, permissions, menus, tenant), login/logout/sync actions, auth status tracking (`idle`/`syncing`/`ready`). |
| `tenant-scope.ts` | `useTenantScopeStore` | Super-admin's current browsing scope: `tenantId` (number | null) + `includeHiddenTenants` flag. Written by `TenantScopeOutlet` in router, read by httpClient request interceptor. |

**Rule:** Store files are named after the domain concept (auth / tenant-scope), not "store". Stores use Zustand v5's `create` — no slices, no middleware. Keep stores flat; prefer multiple small stores over one large one.

### `src/components/` — Shared UI Components

```
components/
├── brand-mark.tsx        # App brand logo/wordmark
├── chat-markdown.tsx     # Markdown renderer for chat messages
├── status-tag.tsx        # Status badge/tag (online/offline/enabled/disabled)
└── status-tag.test.tsx   # Test file (manually maintained, no test framework installed)
```

**Rule:** Shared UI components live here, NOT in `views/`. Page-specific sub-components stay co-located in their view directory. If a component is used by 2+ views, extract it to `components/`.

### `src/layouts/` — Page Layouts

| File | Purpose |
|------|---------|
| `dashboard-layout.tsx` | `DashboardLayout`: renders Sider (sidebar menu from auth store), Header (app title, user dropdown, tenant scope switcher), Content (`<Outlet />`). Handles sidebar collapse, responsive breakpoints, super-admin tenant-browsing menu generation. |

**Rule:** Layouts go in `layouts/`, NOT in `views/` or `components/`. There is exactly one layout component; the router uses it as the parent wrapper for all authenticated routes.

### `src/views/` — Page Components

Each subdirectory is a feature/route page. The directory name is kebab-case. The entry point is `index.tsx`, which exports a named component matching the pattern `{FeatureName}Page` (e.g., `DeviceManagementPage`, `KnowledgeBasePage`).

Views are lazy-loaded in `router/index.tsx` via `React.lazy()`.

```
views/
├── login/                          # LoginPage — authentication form
├── force-password-change/          # ForcePasswordChangePage — first-login password reset
├── dashboard/                      # (dashboard, if present)
├── device-management/              # DeviceManagementPage — device list, CRUD, groups, apps, wake-words
├── device-authorization-center/    # DeviceAuthorizationCenterPage — auth requests, authorization mgmt
├── application-management/         # ApplicationManagementPage + monitor-dashboard, use-agent-audio hook, playback-guard
├── command-management/             # Multi-page: CommandWorkspacePage, PointManagementPage,
│                                   #   CommandExportManagementPage + tasks, groups, control-command,
│                                   #   command-export-state, task-step-form-list
├── knowledge-base/                 # KnowledgeBasePage — document upload, indexing, recall
├── knowledge-base-settings/        # KnowledgeBaseSettingsPage
├── asr-management/                 # AsrManagementPage
├── asr-settings/                   # AsrSettingsPage
├── tts-management/                 # TtsManagementPage
├── tts-settings/                   # TtsSettingsPage + tts-voice-capabilities
├── llm-management/                 # (re-exports LlmSettingsPage as LlmManagementPage from llm-settings)
├── llm-settings/                   # LLM model selection & config
├── settings-llm/                   # LlmSettingsAdminPage — admin-level LLM provider settings
├── model-management/               # ModelManagementPage
├── resource-management/            # ResourceManagementPage
├── scrolling-text-management/      # ScrollingTextManagementPage
├── app-update-management/          # AppUpdateManagementPage
├── tenant-management/              # TenantManagementPage
├── employee-management/            # EmployeeManagementPage
├── account-applications/           # AccountApplicationsPage
├── log-management/                 # LogManagementPage
├── minio-settings/                 # MinioSettingsPage
├── third-party-chatbot-settings/   # ThirdPartyChatbotSettingsPage
├── media-devices.ts                # (standalone flat view)
├── llm-management.ts               # (re-export shim, not a directory)
├── tts-realtime-playback.ts        # (standalone flat view)
├── asr-settings.ts
├── model-management.ts
├── ...                             # Additional re-export shims
```

**Rule:** View directories are named kebab-case matching the feature name. Each directory's `index.tsx` is the default view. `index.tsx` exports a named component (not default export). Additional files in the same directory are helper components, hooks, or utility modules scoped to that view.

**Rule:** Do NOT put layouts or shared components in `views/`. Keep views focused on page-level composition — they import from `components/`, `api/modules/`, and `store/`.

**Rule:** Standalone `.ts` files at the `views/` root are re-export shims (backward compatibility or aliases). New views MUST be a directory with an `index.tsx`.

### `src/router/` — Route Configuration

| File | Purpose |
|------|---------|
| `index.tsx` | `AppRouter` component. Defines route tree with `react-router-dom` v6 `<Routes>`. Guards: `AuthGuard` (redirects unauthenticated), `GuestGuard` (redirects authenticated away from login), `PermissionGuard` (checks permission string), `AuditLogGuard` (audit log permission), `SuperuserGuard` (super-admin only). `TenantScopeOutlet` manages the tenant-scope store lifecycle. All pages are lazy-loaded. |

### `src/styles/` — Global CSS

| File | Purpose |
|------|---------|
| `index.css` | Tailwind base/components/utilities directives, antd component overrides (`Card`, `Table`, `Button`, `Tag`, `Modal`, `Form`, `Input`, `Pagination`, `Segmented`, `Switch`, `Message`, `Notification`, `Descriptions`, `Empty`, `Dropdown`, `Select`, `Layout`), fluid typography scale (`text-fluid-*`), `.page-hero` / `.page-section-title` utility classes, dark sidebar menu theme (`.app-sidebar-menu`, `.app-sidebar-menu-popup`), `.task-step-card` drag-and-drop styles, `.chat-markdown` / `.chat-code-block` styles, `.custom-scrollbar` utility. |

### `src/assets/` — Static Imports

Static files imported by components (e.g., `hero.png`, `typescript.svg`, `vite.svg`). Not for `public/`-style static serving.

### `scripts/` — Standalone Test Scripts

```
scripts/
├── *.mjs        # Standalone Node.js test scripts (no test framework; plain .mjs with assertions)
├── test-*.mjs   # Unit/simulation tests for specific features
└── *test.mjs    # Additional test files
```

**Note:** The project does NOT use vitest or jest. All "tests" are standalone `.mjs` scripts run directly with `node`. These test data transformations, format outputs, and static behavior — not React component rendering.

## Key Architectural Patterns

### Data Flow
```
View (useState + useEffect)
  → API Module (async fetch* functions)
    → httpClient (axios instance)
      → Request interceptor (token, tenant-scope)
        → Backend API
      ← Response interceptor (401 redirect, media URL normalization)
    ← ApiResponse<T>
  ← typed data
```

- No React Query or SWR. Data fetching uses `useState` + `useEffect` directly in components.
- API modules export plain async functions, not hooks.
- Auth state is read synchronously via `useAuthStore.getState()` in interceptors (not `useAuthStore()` which would be invalid outside React).

### Conventions

| Convention | Standard |
|------------|----------|
| API module name | kebab-case matching backend resource (e.g., `ai-models.ts`, `llm-providers.ts`) |
| View directory name | kebab-case feature name (e.g., `device-management/`, `knowledge-base-settings/`) |
| View component export | Named export `{FeatureName}Page` — never `export default` |
| HTTP client import | `import { httpClient } from '../client';` |
| API types | Co-located in the API module file, exported as interfaces/type aliases |
| Fields | camelCase (TypeScript), snake_case in URL params |
| Icons | `@tabler/icons-react` exclusively, typed via `vite-env.d.ts` augmentation |
| CSS | Tailwind utility classes for layout/spacing, `brand-*` color palette, antd components styled via theme + global overrides |
| Layout | `DashboardLayout` wraps all authenticated routes as parent `<Route>` |
| Guards | Auth, permission, superuser, guest — all in `router/index.tsx` as wrapper components |
| State management | Zustand v5 with `create`, no middleware, multiple small stores |

### Adding a New Feature

1. Create API module: `src/api/modules/<resource>.ts` — types + fetch functions
2. Create view: `src/views/<feature>/index.tsx` — named export `{FeatureName}Page`
3. Add route: `router/index.tsx` — `React.lazy()` import + `<Route>` element
4. (If needed) Create shared component: `src/components/<component>.tsx`
5. (If needed) Create layout: `src/layouts/<layout>.tsx`
