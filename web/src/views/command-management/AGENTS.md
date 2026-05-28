[views](../AGENTS.md) > **command-management**

# command-management AGENTS.md

## OVERVIEW

控制指令工作台。一个 `workspace.tsx`（48KB / 1133 行）实际承载 3 条二级路由（`/commands/{groups,control,tasks}`），通过 URL 区分子模块；`points` 与 `export` 单独成页。

## STRUCTURE

```
command-management/
├── index.tsx                  # 模块出口：导出 4 个 Page + 默认 PointManagementPage
├── workspace.tsx              # groups / control / tasks 三合一工作台主体
├── groups.tsx                 # 指令分组面板（嵌入 workspace）
├── tasks.tsx                  # 任务列表面板（嵌入 workspace）
├── task-step-form-list.tsx    # 任务步骤表单（嵌入 tasks）
├── points.tsx                 # 点位管理（独立路由 /commands/points）
├── export.tsx                 # 导入/导出（独立路由 /commands/export）
├── command-export-format.ts   # 导入/导出 JSON 格式定义
└── command-export-state.ts    # 导出本地 state（仅 export 页用）
```

## CONVENTIONS

- **三合一 workspace**：`workspace.tsx` 根据当前路由（`useLocation().pathname`）切换面板（groups / control / tasks），保留同一布局壳。改动这里要**所有三条路由都验证一遍**。
- **导出/导入**：JSON 格式由 `command-export-format.ts` 强约束，新增字段必须同时改导出格式与导入解析。
- **分类下拉**：分类枚举来自后端，前端在新增分类成功后必须立即把新分类**同步到本地分类集合**，否则筛选/编辑下拉要等刷新才出现。

## ANTI-PATTERNS

- ❌ 拆 `workspace.tsx` 为多文件路由：现有约定是单文件 + URL 切面板，方便共享头/尾与状态。
- ❌ 给 `task-step-form-list.tsx` 加全局 store：表单 state 全部在 `tasks.tsx` 里管理，子组件靠 props 透传。
- ❌ 在 `export.tsx` 用 `httpClient`：导出走 `/commands/control/export/` 返回 JSON，**导入** `/commands/control/import/` 走 `multipart`，要谨慎处理。

## NOTES

- 路由 `/commands/task-lists` 已下线，但路由树里仍有遗留键；`router/index.tsx` 的 `hiddenRouteMenuPaths` 在跳转时会跳过它，不要复活。
- `workspace.tsx` 是仓库内最大的 tsx 文件之一（1133 行），diff 噪声很大；建议改动前先用本文件 + `groups.tsx` / `tasks.tsx` 拆解阅读。
