# 修复 Codex 与 OMP 的 GitNexus MCP 接入

## Goal

让 Codex 和 Oh My Pi（OMP）会话都能启动本机 GitNexus MCP Server，直接使用已存在的 `could_frontend_big` 知识图谱，不再写入“resource unavailable”降级说明。

## Background

- `gitnexus 1.6.9` 已全局安装，仓库索引与当前提交 `941a69a` 一致。
- `codex mcp list` 显示尚未配置任何 MCP Server。
- OMP 17.1.7 会从当前 profile 的用户目录 `~/.omp/agent/mcp.json` 读取用户级 MCP 配置；该文件目前不存在。
- OMP 原生配置契约为 JSON 顶层 `mcpServers`，stdio server 使用 `command`、`args` 与可选 `enabled`。

## Requirements

- 在 Codex 用户级配置中注册名为 `gitnexus` 的 stdio MCP Server。
- 在 OMP 当前默认 profile 的用户级配置中注册同名 GitNexus stdio MCP Server。
- 两端均复用全局安装的 `gitnexus mcp`，避免每次启动通过 `npx` 下载或解析最新版。
- 不改动业务代码、现有 GitNexus 索引或用户已有的无关配置。
- 明确说明已打开的 Codex/OMP 会话需要重启才能加载新 MCP 工具。

## Acceptance Criteria

- [x] `codex mcp list` 能列出已启用的 `gitnexus`，命令为 `gitnexus mcp`。
- [x] `~/.omp/agent/mcp.json` 是合法 JSON，并包含已启用的 `gitnexus` stdio server。
- [x] GitNexus MCP 进程可启动并完成 MCP `initialize` 握手，且能列出 GitNexus tools/resources。
- [x] GitNexus 索引状态仍为 up-to-date。
- [x] 仓库现有未提交业务改动不被修改。

## Out of Scope

- 不安装或升级 GitNexus、Codex、OMP 或 Trellis。
- 不为其他编辑器或 OMP named profile 批量注册 MCP。
