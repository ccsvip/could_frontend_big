# Sentry MCP + Codex 集成教程

> 适用场景：让 Codex 读取和分析 Sentry issue、event、trace、release，并在必要时通过 Sentry API 修改 issue 状态。

## 1. 先分清三种凭证/配置

| 名称 | 用途 | 放在哪里 | 是否能修改 issue 状态 |
| --- | --- | --- | --- |
| DSN | 应用上报错误到 Sentry | 前端/后端运行时配置 | 不能 |
| Sentry MCP | 让 Codex 查询 Sentry 数据 | Codex MCP 配置 | 取决于 MCP 工具能力 |
| `SENTRY_AUTH_TOKEN` | 调用 Sentry REST API | 本机环境变量或 CI Secret | 可以，取决于 token 权限 |

不要把 DSN 当成 API token。DSN 用于错误上报，不能 Resolve issue。

## 2. 安装 Sentry MCP

在终端执行：

```bash
codex mcp add sentry -- npx -y mcp-remote@latest https://mcp.sentry.dev/mcp
```

这会在 Codex 的 MCP 配置中添加一个名为 `sentry` 的远程 MCP server。重启 Codex 后，通常会进入 Sentry OAuth 授权流程。

如果需要手动配置，可以编辑 `~/.codex/config.toml`：

```toml
[mcp_servers.sentry]
command = "npx"
args = ["-y", "mcp-remote@latest", "https://mcp.sentry.dev/mcp"]
```

然后重启 Codex。

## 3. 在 Codex 里怎么用 Sentry MCP

配置完成并授权后，可以直接让 Codex 查询 Sentry：

```text
查一下 cancerwake 组织最近的 unresolved issues
```

```text
分析这个 issue 的根因：PYTHON-DJANGO-1
```

```text
查看这个 issue 最近 5 个事件，并按环境和 release 汇总
```

```text
查看某个 trace 下相关 spans 和 logs
```

注意：MCP 当前可能只暴露查询、分析类工具；是否支持修改状态取决于你安装的 MCP server 能力。如果没有写入工具，就需要用 Sentry REST API。

## 4. 获取 `SENTRY_AUTH_TOKEN`

1. 打开 Sentry Auth Tokens 页面：
   `https://sentry.io/settings/account/api/auth-tokens/`
2. 点击 `Create New Token`。
3. 根据用途勾选权限。

建议权限：

```text
org:read
project:read
event:read
project:write
```

其中，修改 issue 状态通常需要写权限。只读分析不需要给写权限。

创建后复制 token。token 只会完整显示一次。

## 5. Windows PowerShell 使用方式

### 临时设置，推荐

只在当前 PowerShell 窗口有效，关闭后失效：

```powershell
$env:SENTRY_AUTH_TOKEN="sntryu_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

适合临时让 Codex 调 API。

### 用户环境变量，长期使用

只对当前 Windows 用户生效：

```powershell
[Environment]::SetEnvironmentVariable("SENTRY_AUTH_TOKEN", "sntryu_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")
```

设置后需要重新打开终端或重启 Codex。

### 不建议系统环境变量

系统环境变量对更多进程/用户可见。除非是专用 CI 机器或专用服务器，否则不要把 Sentry token 放到系统环境变量。

## 6. 用 API 修改 issue 状态

如果 MCP 没有提供写入工具，可以用 Sentry REST API。

已知 issue group id 时：

```powershell
$headers = @{ Authorization = "Bearer $env:SENTRY_AUTH_TOKEN" }
$body = @{ status = "resolved" } | ConvertTo-Json

Invoke-RestMethod `
  -Method Put `
  -Uri "https://us.sentry.io/api/0/issues/<issue_group_id>/" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

示例：把 issue 标记为已解决：

```powershell
$headers = @{ Authorization = "Bearer $env:SENTRY_AUTH_TOKEN" }
$body = @{ status = "resolved" } | ConvertTo-Json

Invoke-RestMethod `
  -Method Put `
  -Uri "https://us.sentry.io/api/0/issues/7531093633/" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

不要把真实 token 写进命令历史、源码、`.env` 或 wiki。

## 7. 常见工作流

### 修复生产 issue

1. 让 Codex 读取 Sentry issue。
2. 根据 stacktrace 回到源码查根因。
3. 修改代码。
4. 使用项目要求的命令验证。
5. 部署或重启服务。
6. 确认 Sentry 没有新增同类事件。
7. 用 API 或 UI 把 issue 标记为 `resolved`。

### 提交信息自动关闭 issue

如果 Sentry 已绑定 Git 仓库，可以在 commit message 或 PR merge message 里写：

```text
Fixes PYTHON-DJANGO-1
```

合并后 Sentry 可以自动关联并关闭 issue。实际效果取决于 Sentry 与代码仓库的集成配置。

## 8. 安全注意事项

- `SENTRY_AUTH_TOKEN` 是敏感凭证，泄露后要立即吊销。
- 不要把 token 发到聊天、文档、Git、截图或日志里。
- 不要把 token 写到项目根 `.env`，本项目根 `.env` 只放宿主端口。
- 后端运行时 DSN 如需配置，应该放在 `backend/.env`，但 DSN 不是 API token。
- 给 token 最小权限。只读分析用只读权限，需要 Resolve issue 时再临时给写权限。
- 临时 token 用完后及时删除。

## 9. 排错

### Codex 看不到 Sentry 工具

检查 MCP 配置：

```toml
[mcp_servers.sentry]
command = "npx"
args = ["-y", "mcp-remote@latest", "https://mcp.sentry.dev/mcp"]
```

然后重启 Codex。

### OAuth 授权失败

- 确认浏览器能访问 Sentry。
- 确认当前账号有目标组织权限。
- 重新运行 `codex mcp add sentry ...`。

### API 返回 401

- token 不正确或已吊销。
- 环境变量没有在当前终端生效。
- PowerShell 变量名写错，应为 `SENTRY_AUTH_TOKEN`。

### API 返回 403

- token 权限不足。
- 尝试给 token 增加 `project:write`，或换有权限的 Sentry 账号生成 token。

### issue 状态改了但又重新打开

说明同类错误再次发生。应回到 Sentry 查看 `Last Seen`、event、release 和部署时间，确认修复是否已部署到触发环境。

