# Design: 智能体联网搜索开关

## Architecture

```
LLMModel.enable_web_search          (平台能力闸门)
        AND
AgentApplication.enable_web_search  (智能体产品闸门)
        │
        ├─ 网页调试 send  → conversation.application.enable_web_search
        └─ 设备实时 LLM → runtime_config['enable_web_search']
                │
                └─ build_llm_request_payload(enable_web_search=…)
```

不引入会话级字段；不改变 `build_llm_request_payload` 内部搜索参数形状。

## Data Model

### `AgentApplication.enable_web_search`

- Django: `BooleanField('是否启用联网搜索', default=False)`
- API camelCase: `enableWebSearch`
- 进入：
  - `AgentApplicationSerializer` fields
  - `build_publish_config()` → `enable_web_search`
  - `runtime_config()` 回退：`config.get('enable_web_search', self.enable_web_search)`

### Migration

1. `AddField` default=False
2. `RunPython`：对每个 `AgentApplication`，若 `llm_model_id` 且 `llm_model.enable_web_search` 则置 `True`
3. **不**批量改写 `published_config` JSON（避免大表扫写与半发布状态混乱）；运行时用 `runtime_config` 回退到模型字段。运营若要锁定发布态，重新发布即可。

## Backend Contracts

### Serializer

- `enableWebSearch = BooleanField(source='enable_web_search', required=False)`
- 不在 serializer 里强制「模型未支持则拒绝 true」——AND 在请求路径生效即可；UI 负责禁用。避免超管改模型能力后历史 true 触发校验失败。

### Effective helper（建议）

```python
def effective_enable_web_search(*, model, agent_enabled: bool) -> bool:
    return bool(getattr(model, 'enable_web_search', False) and agent_enabled)
```

或内联 AND，保持调用点清晰。

### Call sites

| 路径 | 当前 | 改为 |
|------|------|------|
| `ChatConversation` send (`views.py`) | `model.enable_web_search` | `model.enable_web_search and (application.enable_web_search if application else True)` — **无 application 的裸会话**保持仅模型闸门，兼容现有 chat |
| `_prepare_device_llm_session` | `model.enable_web_search` | `model.enable_web_search and bool(runtime_config.get('enable_web_search', False))` |
| `run_llm_model_test` / 平台测速 | 仅模型 | **不变** |
| 标题/摘要生成 | 复用 send 里的 `enable_web_search` 变量 | 随主对话变量变化（主对话关则旁路也关） |

裸会话（`conversation.application is None`）策略：保持「仅模型」，避免破坏 `/chat` 独立对话。智能体调试会话始终有 `application`。

### Publish / runtime

- `build_publish_config` 增加 `'enable_web_search': self.enable_web_search`
- `runtime_config` 增加回退键
- `is_published_current` 自动因 `build_publish_config` 变化而检测草稿/发布差

## Frontend

### Types (`applications.ts`)

- `AgentApplicationRecord.enableWebSearch: boolean`
- `AgentApplicationPayload.enableWebSearch?: boolean`

### State & save (`application-management/index.tsx`)

- `const [enableWebSearch, setEnableWebSearch] = useState(false)`
- `applyApplicationState` / dirty / mismatch / `handleSaveConfig` payload 同步
- 从 `llmOptions` 推导当前模型是否支持：

```ts
const selectedModelSupportsWebSearch = useMemo(() => {
  if (!llmModelId || !llmOptions) return false;
  for (const p of llmOptions.providers || []) {
    const m = (p.models || []).find((x) => x.id === llmModelId);
    if (m) return Boolean(m.enableWebSearch);
  }
  return false;
}, [llmModelId, llmOptions]);
```

### UI block（编排 tab，`platform_llm` 分支内、模型 Select 后）

```
联网搜索                                    [Switch]
开启后模型可检索公网；关闭可降低首字延迟
[disabled 时] 当前模型未开通联网能力，请先在 LLM 设置中开启
```

- `disabled={!canUpdate || !selectedModelSupportsWebSearch}`
- 第三方后端：不渲染（已在 `platform_llm` 条件块内）
- 文案不用 `enable_search`；Tooltip 可写「对应请求参数 enable_search / web_search」

### Dirty / publish labels

- mismatch 文案：`联网搜索`
- 与 temperature 等同级纳入 `isDirty`

## Compatibility

- 旧客户端不传 `enableWebSearch` → serializer default/omit，保留 DB 值
- 旧 `published_config` 无键 → `runtime_config` 回退草稿字段（迁移后草稿已回填）
- 模型级开关关闭后，即使智能体 true，请求仍不联网

## Trade-offs

| 选项 | 取舍 |
|------|------|
| 网页调试读草稿 vs 发布态 | 与 temperature/prompt 一致：保存即调试，设备要发布 |
| 裸 chat 会话 | 仅模型闸门，避免扩大范围 |
| 不校验「模型不支持却 true」 | 配置可保留；运行时 AND；超管改模型能力更平滑 |
| 不改写 published_config | 迁移简单；极少数「已发布但从未再发布」的设备在迁移后跟草稿回填值，与 `runtime_config` 对缺键回退一致 |

## Rollback

- 回滚 migration 去掉字段；前端隐藏开关
- 或临时在 send/realtime 忽略 agent 字段（仅模型）作为热修

## Test Plan (design-level)

- API create/update/read `enableWebSearch`
- migration data：模型 true/false/null
- `build_llm_request_payload` 间接：agent false → 无 search keys
- publish snapshot 含字段；runtime_config 缺键回退
- 前端：类型编译；可选不强制 E2E
