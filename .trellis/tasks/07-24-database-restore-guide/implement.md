# 数据库恢复操作手册实施计划

## Implementation Checklist

- [ ] 1. 复核 PRD 中环境事实与实际 `docker-compose.yaml`、`.env`、`backend/.env` 一致，页面中不写入密码。
- [ ] 2. 在根目录新增 `database-restore-guide.html`，完成语义化页面骨架、离线 CSS token、响应式导航与根因摘要。
- [ ] 3. 写完整 Navicat 方案：连接/SSH 隧道、停止写服务、重新备份、重建库、恢复、验证、重启及菜单版本差异说明。
- [ ] 4. 写完整命令行方案：源端 `pg_dump`、`docker cp`、`scp`、目标端恢复、验证、清理临时文件及失败重做。
- [ ] 5. 补充四类报错解释、危险操作确认框、媒体与 `.env` 边界、常见故障表和最终验收清单。
- [ ] 6. 实现无依赖复制按钮、活动目录高亮和复制结果 `aria-live`；脚本不可用时内容仍完整可读。
- [ ] 7. 静态校验 HTML 结构、敏感信息、关键命令和已知配置值；检查 diff 只包含任务文档与单个 HTML。
- [ ] 8. 使用浏览器在桌面与 375px 视口截图检查：无页面级横向滚动、代码块可滚动、目录可用、内容不遮挡；验证复制交互和 reduced-motion。
- [ ] 9. 运行 GitNexus `detect_changes`，确认新增静态手册未影响业务符号或执行流。

## Validation Commands

```powershell
# 文件与敏感信息检查
rg -n "1314520sm|password\s*=|POSTGRES_PASSWORD=" "./database-restore-guide.html"
rg -n "pg_dump|pg_restore|docker compose stop backend celery_worker celery_beat|digital_human|5433" "./database-restore-guide.html"

# Git 范围检查
git status --short
git diff --check
```

浏览器验证使用本地文件 URL 或仓库内临时静态服务器，视口至少覆盖 1440×900、768×1024、375×812。验证 `document.documentElement.scrollWidth <= window.innerWidth`、复制按钮状态和控制台无错误。

## Risk And Rollback Points

- 风险最高的是文档命令误导用户覆盖错误数据库；所有删除/重建命令前必须显式显示主机、路径、库名核对步骤。
- Navicat 不同版本的 UI 名称存在差异；用功能描述兜底，不承诺完全一致的按钮位置。
- 二进制 dump 不能通过旧版 PowerShell 管道重定向导出；固定采用容器内文件加 `docker cp`。
- 用户明文提供过 SSH 密码，但任何新增文件不得包含该值。
- 回滚代码只需删除新增 HTML；本任务不自动执行任何远程或数据库变更。

## Review Gate

实现开始前由用户确认：交付为根目录单文件 HTML；不接入管理后台；不自动操作虚拟机数据库；两套方案均保留，其中 Navicat 方案优先展示、命令行方案标记为更稳妥。
