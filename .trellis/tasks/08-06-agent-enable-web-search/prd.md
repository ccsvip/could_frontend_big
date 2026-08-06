# 智能体联网搜索开关

## Goal

在智能体编排页为每个智能体提供「联网搜索」开关，使运营可按智能体开启/关闭公网检索，而不必改平台 LLM 模型配置。关闭后该智能体的请求不再附带 `enable_search` / `web_search`，从而降低不必要的首字延迟。

## Background

- 平台 LLM 模型层已有 `LLMModel.enable_web_search`（`/settings/llm`「请求时开启 enable_search」）。
- 打开后，`build_llm_request_payload` 会写入 `enable_search=true` 与 `search_options.forced_search=true`（chat completions），或 Responses 协议的 `web_search` tool。
- 智能体 `/ai-models/applications/:id` 此前没有独立开关；网页调试与设备实时链路一律跟所选模型走。
- UI 方案 A：编排 tab、标准 LLM 模型下方；新建默认关。
- 存量迁移：按绑定模型 `enable_web_search` 回填，保持升级前行为。

## Requirements

1. **智能体字段**：`AgentApplication` 增加 `enable_web_search`（API：`enableWebSearch`），布尔；**新建默认 `false`**。
2. **生效语义**：实际联网 = `模型.enable_web_search AND 智能体.enable_web_search`。任一侧关闭都不向供应商附加搜索参数。
3. **存量迁移**：`RunPython` 将已有智能体按当前绑定模型的 `enable_web_search` 回填（无模型或模型未支持 → `false`）。已发布配置快照在下次保存/发布前，运行时读取需对缺失键兼容（见 design）。
4. **发布快照**：字段进入 `build_publish_config` / `runtime_config` / `is_published_current` 比较；保存草稿与发布均覆盖该字段。
5. **调用链路**：
   - 智能体关联的网页调试会话 send：按关联应用的**草稿**字段与模型能力做 AND。
   - 设备实时 LLM：按 `runtime_config.enable_web_search` 与模型能力做 AND。
   - 第三方机器人后端：不展示、不生效。
6. **前端 UI（方案 A）**：
   - 位置：编排 tab，仅 `runtimeBackendType === 'platform_llm'`；「标准 LLM 模型」下方、「系统提示词」上方。
   - 样式：标题「联网搜索」+ 一行说明 + 右侧 Switch；技术参数名放 Tooltip。
   - 所选模型 `enableWebSearch === false` 或未选模型 → Switch `disabled` + 灰字提示。
   - 接入 dirty 检测、保存 payload、发布不一致字段名。
7. **API**：读写 `enableWebSearch`；公司 LLM options 已有模型级 `enableWebSearch`，前端用其驱动禁用态。

## Acceptance Criteria

- [ ] 新建智能体默认 `enableWebSearch=false`，保存/读回一致。
- [ ] 迁移后：绑定已开联网模型的存量智能体为 `true`；无模型或不支持的为 `false`。
- [ ] 模型支持且智能体开关打开时，网页调试与设备实时请求体包含搜索参数（与现网 `forced_search` / Responses `web_search` 一致）。
- [ ] 模型支持但智能体开关关闭时，请求体不包含 `enable_search` / `search_options` / Responses `web_search`。
- [ ] 模型不支持联网时，即使智能体字段为 true，请求仍不联网；UI 开关禁用。
- [ ] 发布后设备运行时使用发布快照中的开关；仅改草稿未发布不影响运行时。
- [ ] 旧 `published_config` 缺少该键时，运行时回退到草稿字段（与 `runtime_config` 其它字段模式一致）。
- [ ] 切换为第三方机器人后端时，编排页不展示该开关。
- [ ] Django 测试覆盖：API 字段、迁移回填、智能体关 → payload 无 search；前端类型与保存链路同步。

## Out of Scope

- 不改 `/settings/llm` 模型级开关语义与文案。
- 不改 `forced_search` 策略本身（仍随 enable 一并开启）。
- 不给标题生成 / 摘要 / 回答后建议问题等旁路 LLM 单独做产品级联网配置。
- 不做按会话临时覆盖联网。
- 不改第三方机器人厂商侧联网能力。

## Key Decisions

| 决策 | 选择 |
|------|------|
| UI 位置/样式 | 方案 A：编排 tab，模型下方，能力说明 + Switch |
| 新建默认 | `false` |
| 存量迁移 | 跟随绑定模型 `enable_web_search` |
| 生效语义 | 模型能力 AND 智能体开关 |
| 网页调试 | 读应用草稿字段（保存后即调试生效；设备仍需发布） |
