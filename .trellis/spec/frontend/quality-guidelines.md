# Quality Guidelines

> Code quality standards, forbidden patterns, and build requirements for the could_frontend project.

---

## Overview

This document records the project's concrete quality standards, gathered from real codebase conventions enforced by design tokens, build scripts, and code review. These rules exist because the team has found that unchecked patterns (hardcoded sizes, mismatched icon sets, `!important` overrides) accumulate into maintenance drag.

---

## Code Standards

### Icon Library

- **Exclusive source**: `@tabler/icons-react` with `Icon` prefix.
  ```tsx
  // Correct
  import { IconDatabase, IconEdit, IconPlus } from '@tabler/icons-react';
  ```
- **Never** import `@ant-design/icons` or `lucide-react`. The codebase already enforces this — grep confirms zero `@ant-design/icons` imports remain.
- `@tabler/icons-react` SVGs are fixed at 24px but scale correctly inside `.anticon` containers via a global style in `web/src/styles/index.css` (`.anticon > svg { font-size: 1em; }`).

### Status Indicators

- **Always** use `<StatusTag />` from `web/src/components/status-tag.tsx` for business status:
  - `online` / `offline`
  - `active` / `inactive`
  - `bound` / `unbound`
  - `pending`
- The component renders a consistent pill with dot, border, and `text-fluid-xs` typography. All color classes are pre-configured per status type.
- **Never** use inline `<Tag color="...">` or ad-hoc color class strings for these statuses.
- StatusTag is imported from `../../components/status-tag` and used in `web/src/views/device-management/index.tsx`, `web/src/views/application-management/index.tsx`, `web/src/views/knowledge-base/index.tsx`, and others.
- For non-business tags (categories, labels), `<Tag color="...">` from Ant Design is acceptable, but prefer StatusTag whenever the value represents a business state.

### Fluid Typography

Use `text-fluid-*` classes defined in `web/src/styles/index.css` (lines 661-666). These use `clamp()` for viewport-responsive sizing:

| Class | CSS `clamp()` | Usage |
|-------|--------------|-------|
| `text-fluid-xs` | `clamp(10px, 0.52vw + 6px, 14px)` | Timestamps, device codes, metadata |
| `text-fluid-sm` | `clamp(12px, 0.52vw + 8px, 16px)` | Button labels, stat labels, secondary descriptions |
| `text-fluid-base` | `clamp(13px, 0.52vw + 9px, 18px)` | Body text, detail values, table cell content |
| `text-fluid-lg` | `clamp(14px, 0.62vw + 10px, 20px)` | Section titles (includes `font-weight: 600`) |
| `text-fluid-xl` | `clamp(18px, 0.83vw + 12px, 28px)` | Page titles |
| `text-fluid-stat` | `clamp(22px, 1.04vw + 14px, 36px)` | Statistic numbers on dashboard cards |

**Forbidden**:
- Hardcoded pixel sizes via `text-[13px]`, `text-[16px]`, `text-[10px]`, `text-[11px]` (still present in legacy code at `web/src/views/knowledge-base/index.tsx`, `web/src/views/login/index.tsx`, `web/src/views/tenant-management/index.tsx`, and others — new code must not add more).
- Tailwind named sizes like `text-xs`, `text-sm`, `text-base` when the `text-fluid-*` equivalent exists.

Refer to `web/src/styles/index.css` lines 656-666 for the authoritative definition.

### Color Tokens

- **Always** use `brand-*` palette defined in `web/tailwind.config.ts`:
  ```tsx
  // Correct
  <span className="text-brand-700 bg-brand-50 border-brand-200">...</span>
  ```
- The brand palette aligns with `colorPrimary: '#0f766e'` set in `web/src/main.tsx` (antd theme token, line 12).
- **Never** use `teal-*` classes — the codebase is teal-free (confirmed by grep — zero matches in `web/src/views/`). The pre-commit guard `scripts/check-tailwind-tokens.js` blocks net increases in `teal-*`.
- **Never** hardcode `#0f766e` hex literals in component files. The only allowed locations are:
  - `web/src/main.tsx` — antd theme token `colorPrimary`
  - `web/src/styles/index.css` — scoped CSS classes (pagination, scrollbar, card borders, etc.)
- One remaining legacy violation of this rule exists in `web/src/views/application-management/index.tsx` line 1667 (`Badge count color="#0f766e"`). Do not add more.

### No `!important` Tailwind

- **Never** use the Tailwind `!` prefix (`!p-0`, `!bg-brand-600`, `!rounded-xl`) to force-override Ant Design defaults in TSX files.
- When Ant Design component overrides are needed, add a scoped CSS class in `web/src/styles/index.css` using the component's BEM selector (e.g., `.ant-modal-content { ... }`). This is the project's established pattern — see lines 39-378 of `styles/index.css` for examples covering Card, Table, Button, Tag, Form, Input, Modal, Switch, Pagination, Segmented, Menu, and more.
- The pre-commit guard (`scripts/check-tailwind-tokens.js`) blocks net increases of `!`-prefixed classes in staged `.tsx` files compared to HEAD.

### Page Layout Helpers

- Use `page-hero` and `page-section-title` CSS classes from `web/src/styles/index.css` for consistent page sectioning:
  - `.page-hero`: Top page banner with gradient and brand highlight. Used extensively in `web/src/views/` (e.g., `llm-management/index.tsx`, `asr-management/index.tsx`, `log-management/index.tsx`, `app-update-management/index.tsx`, `tts-management/index.tsx`).
  - `.page-section-title`: Unified section heading style (`font-size: 13px`, uppercase, muted). Used in `web/src/views/app-update-management/index.tsx` and `web/src/views/third-party-chatbot-settings/index.tsx`.

---

## Build Requirements

- **`npm run build`** in `web/` must pass. It runs `tsc -b` (strict type checking) followed by `vite build`.
- TypeScript strict mode is enabled in `web/tsconfig.app.json`:
  ```json
  {
    "compilerOptions": {
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true
    }
  }
  ```
- Pre-commit guard: `scripts/check-tailwind-tokens.js` checks staged `.tsx` files for:
  - Net increase in `!`-prefixed Tailwind classes (against HEAD)
  - Net increase in `teal-*` classes (against HEAD)
  - Blocked output prints file-level deltas; bypass with `git commit --no-verify`.

---

## Forbidden Patterns

| Pattern | Why | Real Violations Still in Codebase (do not add more) |
|---------|-----|------------------------------------------------------|
| Hardcoded pixel font sizes (`text-[13px]`, `text-[10px]`, `text-[11px]`) | Breaks fluid typography system. Use `text-fluid-*` classes instead. | `web/src/views/knowledge-base/index.tsx` (multiple `text-[10px]`, `text-[11px]`, `text-[13px]`), `web/src/views/login/index.tsx` (multiple `text-[13px]`), `web/src/views/tenant-management/index.tsx` (multiple `text-[13px]`), `web/src/views/command-management/workspace.tsx` (`text-[16px]`, `text-[17px]`), `web/src/views/device-authorization-center/components/DeviceAuthorizationToolbar.tsx` (`text-[11px]`, `text-[13px]`), `web/src/views/asr-management/index.tsx` (`text-[15px]`), `web/src/views/asr-settings/index.tsx` (`text-[10px]`, `text-[11px]`), `web/src/views/application-management/index.tsx` (`text-[10px]`) |
| Mixed icon libraries in same file | Increases bundle size and visual inconsistency. | None detected — codebase is consistent on `@tabler/icons-react`. |
| Inline `!bg-teal-600` / Tailwind `!` prefix overrides on Ant Design components | Bypasses the centralized CSS override layer in `styles/index.css`. | None detected in views — but guard is in place to prevent regressions. |
| Manual `<Tag color="...">` where `StatusTag` suffices | Inconsistent status visuals across views. | Use StatusTag for `online`/`offline`/`active`/`inactive`/`bound`/`unbound`/`pending` business statuses. |
| Direct `#0f766e` hex literals in component files | Hardcodes the brand color outside token sources (`main.tsx`, `styles/index.css`, `tailwind.config.ts`). | `web/src/views/application-management/index.tsx` line 1667 (`Badge color="#0f766e"`). |
| `teal-*` Tailwind color classes | `teal-*` shares hex values with `brand-*` but is not in the design system. | None remaining in views (pre-commit guard blocks new ones). |
| Inline `style={{ fontSize: ... }}` for text sizing | Bypasses the fluid typography system. | Scattered in older components; new code must not add these. |

---

## Required Patterns

### Import Order Convention

The codebase follows a consistent import order per file. When adding imports to an existing file, insert new imports into the matching section:

1. **Icons** (top of file): `import { IconX } from '@tabler/icons-react';`
2. **Ant Design** (second block): `import { Button, Card, Table } from 'antd';`
3. **React / hooks**: `import { useEffect, useState } from 'react';`
4. **Third-party**: `import dayjs from 'dayjs';`
5. **Project utilities**: `import { StatusTag } from '../../components/status-tag';`
6. **Store**: `import { useAuthStore } from '../../store/auth';`
7. **API types & calls**: `import { fetchDevices } from '../../api/modules/devices';`
8. **Local constants**: `import { statusMap } from './constants';`
9. **Styles / types**: `import type { ColumnsType } from 'antd/es/table';`

### Data Fetching Pattern

- Uses `useState` + `useEffect` with direct axios calls via the `httpClient` wrapper from `web/src/api/client.ts`.
- No React Query or SWR — the project intentionally avoids them.
- Loading state managed with local `useState` booleans.
- Error handling via the axios interceptor (redirects on 401, displays server errors via `message.error`).

### Store Pattern

- Zustand v5 stores in `web/src/store/`:
  - `useAuthStore`: Authentication state (token, user, login/logout actions)
  - `useTenantScopeStore`: Current tenant scope (tenantId)
- No context-based state management.

---

## Common Mistakes

1. **Adding `style={{ color: '#0f766e' }}`** in a component instead of `className="text-brand-700"`.
2. **Using `text-xs` or `text-sm`** alongside `text-fluid-base` — the two systems don't scale together on large monitors.
3. **Adding `!` prefix in TSX** to fix an Ant Design layout issue rather than adding a scoped class in `styles/index.css`.
4. **Importing `@ant-design/icons`** when `@tabler/icons-react` provides the equivalent icon (e.g., `IconPlus` vs `PlusOutlined`).
5. **Creating inline `<span className="... text-\[13px\] ...">`** instead of choosing the appropriate `text-fluid-*` class.
6. **Using `<Tag color="green">在线</Tag>`** inline instead of `<StatusTag type="online" />`.
7. **Hardcoding Tailwind `gap-4` or `space-y-4`** inconsistently — prefer the project's established spacing conventions.

---

## Code Review Checklist

When reviewing frontend changes, verify:

- [ ] All icons come from `@tabler/icons-react`, not `@ant-design/icons` or `lucide-react`
- [ ] Business status uses `<StatusTag />` from `web/src/components/status-tag.tsx`
- [ ] Text sizing uses `text-fluid-*` classes, not `text-[...]` or raw Tailwind `text-xs`
- [ ] Colors use `brand-*` tokens, not `teal-*` or raw `#0f766e`
- [ ] No Tailwind `!` prefix overrides in TSX files
- [ ] No new `teal-*` or `!` classes that would trigger the pre-commit guard
- [ ] TypeScript compiles cleanly (`tsc -b` passes)
- [ ] API types use camelCase fields from `web/src/api/modules/*.ts`
- [ ] Zustand store imports reference `../../store/auth` or `../../store/tenant-scope`, not React context
- [ ] No new hardcoded pixel font sizes (`text-[Npx]`)
