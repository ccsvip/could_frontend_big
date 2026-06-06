# Login Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `/login` into a dark digital-human operations command center with a generated hero image while preserving existing authentication behavior.

**Architecture:** Keep `LoginPage` as the single route component and preserve the existing API calls, form fields, account-application modal, and navigation. Add one project-local raster hero asset and one static guard script so the visual refactor remains scoped to `/login`.

**Tech Stack:** React 18, TypeScript, Vite, Ant Design 5, Tailwind utilities, Node static check scripts, Docker Compose execution only.

---

## File Structure

- Create: `web/scripts/test-login-command-center-static.mjs`
  - Static source guard for the login command center layout, hero asset import, modal preservation, and removal of the old `hero.png` dependency.
- Create: `web/src/assets/login-command-center.png`
  - AI-generated bitmap hero image for the dark command center first screen.
- Modify: `web/src/views/login/index.tsx`
  - Replace the current light login first screen with the dark command center layout.
  - Keep `onSubmit`, `handleApplySubmit`, form payload types, stores, API calls, and modal fields intact.
- Verify only, no planned edits: `web/src/components/brand-mark.tsx`
  - Reuse `BrandMark` with a dark-compatible presentation.
- Verify only, no planned edits: `web/src/main.tsx`
  - Existing Ant Design theme remains valid for the rest of the app.

## Task 1: Add Static Guard For Login Command Center

**Files:**
- Create: `web/scripts/test-login-command-center-static.mjs`
- Test: `web/scripts/test-login-command-center-static.mjs`

- [ ] **Step 1: Write the failing static test**

Create `web/scripts/test-login-command-center-static.mjs` with this exact content:

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const loginSource = readFileSync(resolve(__dirname, '../src/views/login/index.tsx'), 'utf8');

assert(
  loginSource.includes("import loginCommandCenterImage from '../../assets/login-command-center.png';"),
  'login page must import the new command center hero asset',
);

assert(
  !loginSource.includes("import heroLayerImage from '../../assets/hero.png';"),
  'login page must stop depending on the old small hero icon',
);

assert(
  loginSource.includes('const commandCenterNodes = ['),
  'login page must define command center visual nodes for the hero scene',
);

assert(
  loginSource.includes('const operationSignals = ['),
  'login page must define operation signal summaries for the first screen',
);

assert(
  loginSource.includes('aria-label="数字人运维指挥中心主视觉"'),
  'hero scene must expose a stable accessible label',
);

assert(
  loginSource.includes('数字人运维指挥中心'),
  'login first screen must present the command center positioning',
);

assert(
  loginSource.includes('账号入驻申请') &&
    loginSource.includes('提交申请') &&
    loginSource.includes('取消'),
  'account application modal must keep the existing application flow labels',
);

assert(
  loginSource.includes('onFinish={onSubmit}') &&
    loginSource.includes('loginRequest(values)') &&
    loginSource.includes("navigate('/devices', { replace: true })"),
  'login form behavior must keep the existing submit request and navigation',
);

console.log('login command center static checks passed');
```

- [ ] **Step 2: Run the static test to verify it fails**

Run from the repository root:

```bash
docker compose exec web node scripts/test-login-command-center-static.mjs
```

Expected: FAIL with `login page must import the new command center hero asset`.

- [ ] **Step 3: Commit the failing guard**

```bash
git add web/scripts/test-login-command-center-static.mjs
git commit -m "test: 添加登录页指挥中心静态检查"
```

## Task 2: Generate The Command Center Hero Asset

**Files:**
- Create: `web/src/assets/login-command-center.png`

- [ ] **Step 1: Generate the hero image with the built-in image generation tool**

Use this prompt:

```text
Use case: ui-mockup
Asset type: web login page hero image
Primary request: Create a dark digital-human operations command center hero image for a backend management platform.
Scene/backdrop: a cinematic control room with an abstract AI core, device network nodes, subtle data streams, and translucent dashboard panels.
Subject: digital human operations hub, connected devices, model orchestration, knowledge base signals, secure access control.
Style/medium: high-quality 3D cinematic UI concept, refined enterprise software aesthetic, not game-like.
Composition/framing: wide landscape composition, strong visual focus on the left or center, darker negative space on the right for a login panel overlay.
Lighting/mood: dark graphite and black-blue environment, teal system glow, cool white highlights, very small amber alert accents.
Color palette: graphite, deep navy, dark cyan, teal, cool white, restrained amber.
Materials/textures: glass panels, fine grid, brushed dark metal, subtle volumetric light, clean data lines.
Text (verbatim): no text.
Constraints: no logos, no watermark, no readable text, no face close-up, no messy clutter, no bright white background.
Avoid: purple gradient SaaS style, cartoon style, generic stock image, excessive neon, overexposed center.
```

- [ ] **Step 2: Save the selected image in the workspace**

Save the final selected file as:

```text
web/src/assets/login-command-center.png
```

Do not overwrite `web/src/assets/hero.png`.

- [ ] **Step 3: Confirm the asset exists**

Run:

```bash
docker compose exec web node -e "const fs=require('fs'); const p='src/assets/login-command-center.png'; if(!fs.existsSync(p)) throw new Error(p+' missing'); console.log('login command center asset exists')"
```

Expected: PASS with `login command center asset exists`.

## Task 3: Implement The Dark Login Command Center Layout

**Files:**
- Modify: `web/src/views/login/index.tsx`
- Create: `web/src/assets/login-command-center.png`
- Test: `web/scripts/test-login-command-center-static.mjs`

- [ ] **Step 1: Replace the old hero import**

In `web/src/views/login/index.tsx`, replace:

```ts
import heroLayerImage from '../../assets/hero.png';
```

with:

```ts
import loginCommandCenterImage from '../../assets/login-command-center.png';
```

- [ ] **Step 2: Add command center scene data above `LoginPage`**

Add these constants near the existing visual-data constants:

```tsx
const commandCenterNodes = [
  { label: '设备网络', value: 'ONLINE', className: 'left-[8%] top-[18%]', delay: '0s' },
  { label: '模型调度', value: 'SYNC', className: 'right-[12%] top-[24%]', delay: '0.35s' },
  { label: '权限网关', value: 'SECURE', className: 'left-[13%] bottom-[20%]', delay: '0.7s' },
  { label: '知识中枢', value: 'READY', className: 'right-[16%] bottom-[18%]', delay: '1.05s' },
];

const operationSignals = [
  { label: '终端状态', value: '实时在线', tone: 'text-emerald-200' },
  { label: '访问控制', value: '权限同步', tone: 'text-cyan-200' },
  { label: '运维告警', value: '低风险', tone: 'text-amber-200' },
];
```

- [ ] **Step 3: Replace the page shell JSX while preserving handlers and modal**

Keep these existing pieces unchanged:

```tsx
const onSubmit = async (values: LoginForm) => {
  setSubmitting(true);
  try {
    const response = await loginRequest(values);
    login({
      username: response.user.display_name || response.user.username,
      token: response.access,
      refreshToken: response.refresh,
      role: response.user.role,
      permissions: response.user.permissions,
      menus: response.user.menus,
      tenant: response.user.tenant,
      isSuperuser: response.user.is_superuser,
      mustChangePassword: response.user.must_change_password,
    });
    message.success(response.message || '登录成功');
    navigate('/devices', { replace: true });
  } finally {
    setSubmitting(false);
  }
};
```

and:

```tsx
const handleApplySubmit = async () => {
  const values = await applyForm.validateFields();
  setApplySubmitting(true);
  try {
    const response = await applyAccountRequest(values);
    message.success(response.message || '账号申请已提交，管理员会尽快审核');
    setApplyVisible(false);
    applyForm.resetFields();
  } catch {
    // 错误已在拦截器中处理
  } finally {
    setApplySubmitting(false);
  }
};
```

Replace only the visual JSX returned by `LoginPage` with a dark full-screen layout that includes these stable markers:

```tsx
<div className="relative min-h-screen overflow-hidden bg-[#070b12] text-slate-50">
  <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,rgba(20,184,166,0.24),transparent_34%),radial-gradient(circle_at_74%_22%,rgba(245,158,11,0.10),transparent_26%),linear-gradient(135deg,#070b12_0%,#0b1220_46%,#081a1c_100%)]" />
  <div className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:linear-gradient(rgba(148,163,184,0.34)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.34)_1px,transparent_1px)] [background-size:48px_48px]" />

  <main className="relative z-10 flex min-h-screen flex-col px-5 py-6 sm:px-8 lg:px-12">
    <header className="mx-auto flex w-full max-w-7xl items-center justify-between">
      <BrandMark title={APP_TITLE} subtitle="COMMAND CENTER" tone="dark" />
    </header>

    <section className="mx-auto grid w-full max-w-7xl flex-1 items-center gap-8 py-8 lg:grid-cols-[minmax(0,1fr)_430px] lg:gap-12">
      <div className="relative hidden min-h-[520px] min-w-0 lg:block" aria-label="数字人运维指挥中心主视觉">
        {/* image, operation signals, and commandCenterNodes render here */}
      </div>

      <div className="mx-auto w-full max-w-[430px] lg:mx-0">
        {/* existing login form fields render here with dark command-center styling */}
      </div>
    </section>
  </main>

  {/* existing account application Modal remains in this component */}
</div>
```

- [ ] **Step 4: Run the static test to verify the layout markers**

```bash
docker compose exec web node scripts/test-login-command-center-static.mjs
```

Expected: PASS with `login command center static checks passed`.

- [ ] **Step 5: Commit the asset and login layout**

```bash
git add web/src/assets/login-command-center.png web/src/views/login/index.tsx
git commit -m "feat: 升级登录页指挥中心视觉"
```

## Task 4: Verify Build And Responsive Login Page

**Files:**
- Verify: `web/src/views/login/index.tsx`
- Verify: `web/src/assets/login-command-center.png`
- Verify: `web/scripts/test-login-command-center-static.mjs`

- [ ] **Step 1: Run the static login check**

```bash
docker compose exec web node scripts/test-login-command-center-static.mjs
```

Expected: PASS with `login command center static checks passed`.

- [ ] **Step 2: Run the frontend build inside Docker**

```bash
docker compose exec web npm run build
```

Expected: PASS. The command should complete Vite and TypeScript build without unused imports, type errors, or missing asset errors.

- [ ] **Step 3: Start or confirm the full stack**

```bash
docker compose up -d
```

Expected: `web` is reachable through the configured host port.

- [ ] **Step 4: Browser-check `/login` desktop and mobile**

Open:

```text
http://localhost:5175/login
```

Check:

- Desktop: dark command center visual is visible, login panel is readable, no text overlaps.
- Mobile: login panel appears first, background visual does not block inputs or buttons.
- Account application modal opens, closes, and remains readable.

- [ ] **Step 5: Final status check**

```bash
git status --short
```

Expected: no unstaged or untracked files except intentional generated screenshots if a browser tool saved any.
