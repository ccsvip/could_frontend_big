# Journal - cancer (Part 1)

> AI development session journal
> Started: 2026-07-18

---



## Session 1: 修复 Codex 与 OMP 的 GitNexus MCP 接入

**Date**: 2026-07-28
**Task**: 修复 Codex 与 OMP 的 GitNexus MCP 接入
**Branch**: `dev`

### Summary

为 Codex 和 OMP 默认用户配置注册 gitnexus stdio MCP；通过 Codex 列表、OMP /mcp list 与 /mcp test、原生 MCP initialize/tools/resources 握手验证。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

(No commits - planning session)

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 修复智能体标注媒体流式断连

**Date**: 2026-07-28
**Task**: 修复智能体标注媒体流式断连
**Branch**: `dev`

### Summary

将 Annotation 媒体回复块的同步资源序列化移至异步 SSE generator 外，避免 ASGI SynchronousOnlyOperation 断开流；补充媒体块回归测试并验证 Docker 后端测试与前端构建。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `df3f3a7` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: 修复设备状态心跳错误映射

**Date**: 2026-07-28
**Task**: 修复设备状态心跳错误映射
**Branch**: `dev`

### Summary

修复统一 WebSocket 的 device.status.ping 忽略 payload.deviceCode 问题；心跳现在按设备、公司、应用和智能体真实状态返回 1001-1009 错误，可为有效设备恢复状态会话，并补齐在线生命周期与重新校验回归测试。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `165e880` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: 修复百炼索引名称长度错误

**Date**: 2026-07-28
**Task**: 修复百炼索引名称长度错误
**Branch**: `main`

### Summary

将百炼远端索引名改为基于知识库主键的稳定 base36 名称，并在 SDK 边界校验 1 到 20 字符；新增长名称、唯一性和非法边界回归测试。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `ed89f7b` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: 公司侧 CosyVoice 分配与可扩展 TTS 架构

**Date**: 2026-07-30
**Task**: 公司侧 CosyVoice 分配与可扩展 TTS 架构
**Branch**: `dev`

### Summary

新增 TenantTTSProviderGrant 按 TTS 卡片粒度授权公司，有效音色由「启用授权+启用卡片+启用可见音色」派生；数据迁移为存量 active 公司补建阿里云/Qwen 授权并搬迁旧 tts_session_config，CosyVoice 需超管显式分配。建立 tts_authorization 唯一授权入口与 tts_adapters 供应商 seam，CosyVoice 通过 run-task/continue-task/finish-task 接入统一 /ws/realtime/ 并逐块转发音频。统一 realtime 改为按已解析音色所属卡片路由，providerCode 仅做一致性校验，移除对 cosyvoice 的一律拒绝。新增超管卡片授权 API 与前端页面，公司页面按卡片 schema 渲染配置；安卓运行时契约保持冻结。137 条针对性测试通过，前端 npm run build 通过。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `ea290f5` | (see git log) |
| `54d669d` | (see git log) |
| `fd58eaa` | (see git log) |
| `87ff849` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: 修复 CosyVoice TTS 卡片授权测试失败（播种缺失的卡片行）

**Date**: 2026-07-31
**Task**: 修复 CosyVoice TTS 卡片授权测试失败（播种缺失的卡片行）
**Branch**: `fix-bug`

### Summary

Sentry PYTHON-DJANGO-47/-48 (ImportError: TenantTTSProviderGrant) 定位为切分支后未重启 solin_backend 的进程内模块缓存错配，源码无缺陷，已 resolved 并备注根因；顺带发现 test_tts_card_authorization_api 3 条真实失败：0043 建了 CosyVoiceSettings 却从未播种 code='cosyvoice' 的 TTSProvider 行，而超管分配列表是 TTSProvider 行与 adapter 注册表的交集，导致任何新建库都无法分配 CosyVoice。新增 0047_seed_cosyvoice_provider（get_or_create 幂等、reverse=noop），目标模块 19/19 绿，全量 298 tests 由 11F+2E 降至 10F+0E（剩余同名、均为无关的知识库召回失败），现网 id=4 行逐字段无变化。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `1aafbff` | (see git log) |
| `81303ce` | (see git log) |
| `7fa6c83` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete
