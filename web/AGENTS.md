[根目录](../AGENTS.md) > **web**

# web 模块 AGENTS.md

> 详细 FAQ 见同目录 `CLAUDE.md`。本文件是 quick-ref。

## OVERVIEW

React 18 + Vite + TS strict + Antd 5 + Tailwind + Zustand。后台管理 SPA，对接 `/api/v1/*` 与 `/media/*`。

## STRUCTURE

```
web/
├── src/
│   ├── api/          # axios 客户端 + 11 个领域模块
│   ├── components/   # brand-mark / chat-markdown（仅 2 个全局组件）
│   ├── layouts/      # dashboard-layout（认证后外壳）
│   ├── router/       # 路由 + AuthGuard / GuestGuard / PermissionGuard
│   ├── store/        # auth.ts（Zustand 唯一全局 store）
│   ├── styles/       # tailwind 入口 + 自定义 CSS
│   └── views/        # 14 个页面模块（kebab-case 目录 + index.tsx）
├── public/
├── scripts/          # 构建辅助脚本
├── index.html        # Vite 入口
├── vite.config.ts    # 仅配 react 插件 + 代理
└── tsconfig.app.json # strict + noUnused* + isolatedModules
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 加新页面 | `src/views/<domain>/index.tsx` + `src/router/index.tsx` 注册 |
| 加新 API 调用 | `src/api/modules/<domain>.ts`，全部 `import { httpClient } from '../client'` |
| 加全局状态 | 扩 `src/store/auth.ts` 或新建 store（项目目前只有 auth 一个） |
| 改全局拦截 | `src/api/client.ts`（401 自动清登录态 + 跳 `/login`） |
| 改菜单/权限 | **不要在前端配**：菜单与权限来自后端 `/auth/me/`，前端只做展示与守卫 |

## CONVENTIONS

- **TS strict**：`noUnusedLocals` + `noUnusedParameters` + `noFallthroughCasesInSwitch` 全开（见 `tsconfig.app.json`）；不要 `any`。
- **JSX runtime**：`react-jsx`，不要写 `import React from 'react'`，按需 `import { useState }`。
- **路径**：相对 import，**没有**配置 `@/*` 别名。
- **样式**：Tailwind utility 优先；Antd 组件保持默认主题；项目内未配 CSS Modules。
- **请求**：通过 `httpClient` 自动注入 Bearer，401 时自动清 token + 跳 `/login`。
- **登录态持久化**：`localStorage`（`token` / `refreshToken` / `username` / `role` / `permissions` / `menus`）；启动时由 `router/index.tsx` 调 `/auth/me/` 校准。

## ANTI-PATTERNS

- ❌ 用 `fetch` 或新建 axios 实例（除已有的 knowledge-base 下载 helper 外）。
- ❌ 在前端硬编码菜单或权限：菜单/权限/角色三件套**唯一事实来源**是后端。
- ❌ 在 `ResourceManagementPage` 上不传 `key` 复用：图片/视频会串状态。
- ❌ 给 `chat-room` 加本地伪打字机：流式直接按 chunk 实时渲染 Markdown，不要队列模拟。
- ❌ 在 `/login` 之外页面绕过 `AuthGuard` / `PermissionGuard`。

## COMMANDS

```bash
npm run dev      # vite 默认 5173，host 0.0.0.0
npm run build    # tsc -b && vite build（先类型检查再打包）
npm run preview  # 本地预览构建产物
```

## NOTES

- Vite proxy 仅在 `VITE_API_PROXY_TARGET` 存在时启用；compose 内由 nginx/直连转发。
- DEV 模式下 axios 响应拦截器会把 `backend:8000/media/...` 的绝对地址改写成同源 `/media/...`，避免浏览器跨域访问内部容器名。
- `chat-markdown.tsx` 是无依赖的 Markdown 渲染器（自实现），别引入 `react-markdown`，会破坏流式实时刷新约束。
- 发请求 timeout 默认 10s（`client.ts`）；上传/下载等长时操作要在调用处单独覆盖。
