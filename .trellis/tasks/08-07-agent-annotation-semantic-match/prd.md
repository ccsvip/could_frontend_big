# 智能体标注语义匹配

## 目标

智能体标注（`/ai-models/applications/:id` 标注 Tab）在保留精确匹配的前提下，支持对用户问法做语义命中：用户说「你好，请给我介绍一下你们公司」时，可命中标准问「介绍一下你们公司」并返回固定回复，短路 LLM。

换租户 embedding / rerank 模型后，匹配链路不混用向量空间、不静默失效，支持双桶迁移。

## 背景

- 现状：`backend/apps/ai_models/services/annotations.py` 仅做去标点 + casefold 精确相等。
- 命中入口：
  - Web 会话：`find_matching_annotation`
  - 设备 HTTP / 统一实时 WS：`find_matching_published_annotation`（读 `published_annotations`）
- 知识库已配置：`text-embedding-v4`（1024 维）+ `qwen3-vl-rerank`（DashScope）。
- 实测（backend 容器 → DashScope）：embed 单句 p50 ≈ 188ms；rerank 3 候选 p50 ≈ 231ms。

## 需求

### R1 分层匹配

1. **第 1 层精确匹配**（现有逻辑，行为不变）。
2. **第 2 层语义匹配**：对用户 query 调当前租户 embedding 模型，与同 fingerprint 的标注向量做 cosine，取 Top1 且 `score >= threshold` 则命中。
3. 未命中 → 原 LLM / 知识库路径不变。

### R2 模型与配置来源

1. Embedding 解析复用租户知识库设置：`TenantKnowledgeModelSettings.embedding_model`（与 `_embedding_model_for_tenant` 一致）。
2. **不**依赖 `managed_rag_enabled`（百炼开关与标注语义无关）。
3. 无可用 embedding（未分配 / 缺 key / 停用）→ 仅精确匹配。

### R3 阈值与策略（已拍板）

| 项 | 值 |
|---|---|
| 语义默认 | 有可用 embedding 时启用 |
| cosine 阈值 | **0.88**（可按智能体配置覆盖） |
| Rerank | **MVP 不做**；实时路径强制关闭；仅预留策略字段/接口 |
| embed 超时 | **300ms**，超时视为语义未命中，不阻断对话 |
| 命中规则 | 仅 Top1 且过阈值 |

### R4 向量存储与换模型

1. 独立表分桶存储标注向量，按 `embedding_fingerprint` 隔离（`code|model|dimensions`）。
2. 同一标注可并存多模型桶；运行时只比「当前可用 fingerprint」的 ready 向量。
3. 换 embedding 模型：异步/批量建新桶；迁移期 **优先新桶 / 回退旧桶**（旧模型仍可调用时）；否则仅精确匹配。
4. 换 rerank 模型：无持久向量；MVP 不调用 rerank，预留不阻塞。
5. 改 `question`：失效旧 hash 向量并重建当前模型桶。

### R5 发布与运行时一致

1. `publish` 快照写入 ready 向量 + fingerprint；无向量则 `embedding: null`（该条只 exact）。
2. 设备 / 实时读已发布快照；草稿语义不进设备。
3. 快照 fingerprint 与当前租户模型不一致时：若仍能解析并调用快照模型则用之；否则仅精确匹配。
4. 换模型后需重新 publish，设备端才使用新向量。

### R6 失败降级

以下任一情况不得抛错中断对话，语义视为未命中：

- embed API 错误 / 超时
- 无 ready 向量
- 向量维度不一致
- 语义开关关闭

### R7 可观测

命中日志可区分 `matchType=exact|semantic`，语义命中带 `score` 与 `fingerprint`（遵循现有日志脱敏规范）。

### R8 路径覆盖

Web 会话、设备语音 HTTP、统一实时 WebSocket 三处标注命中统一走同一匹配实现。

## 验收标准

- [x] AC1：精确问法仍命中，行为与现网一致。
- [x] AC2：语义改写在阈值内命中同一标注固定回复。
- [x] AC3：近义但不同意图在 0.88 默认阈值下不命中。
- [x] AC4：无 embedding 配置或 embed 失败/超时 → 仅 exact，对话成功继续。
- [x] AC5：创建/更新标注后当前模型向量 ready；改 question 后旧向量不参与匹配。
- [x] AC6：publish 后设备/实时可用快照语义命中；未 publish 的草稿不进设备。
- [x] AC7：租户切换 embedding 模型后双桶迁移；跨 fingerprint 永不混算 cosine。
- [x] AC8：实时路径不调用 rerank；语义未 exact 命中时 embed 超时 ≤300ms 放弃语义。
- [x] AC9：租户数据隔离。
- [x] AC10：自动化测试覆盖 exact / 语义命中 / 误伤不命中 / 降级 / fingerprint 隔离 / 发布快照。

## 非范围

- 标注别名 / 多触发问法 UI（方案 2）
- 小模型语义裁判
- MVP 启用 rerank 实际调用（仅预留）
- 独立向量数据库（pgvector/Milvus）
- 改知识库召回 / 百炼逻辑
- 前端阈值调参大盘（MVP 用默认值）

## 关键决策

1. 只做方案 3（embedding 语义），不做别名。
2. 默认阈值 0.88；有 embedding 则默认开语义。
3. 换模型双桶回退，不用单字段覆盖。
4. MVP 关闭 rerank；实时强制关。
5. embed 超时 300ms → 未命中。
6. 复用租户知识库 embedding 配置，不绑 `managed_rag_enabled`。

## 风险

- 阈值在换 embedding 模型后分布漂移 → 需样本重标定；默认偏严。
- miss 路径固定 +~0.2s（现网实测）→ 可接受；hit 路径通常仍快于 LLM。
- 发布 JSON 含向量体积增大 → 单智能体标注量通常可接受。
- 已发布智能体在未重新 publish 前，`is_published_current` 可能因快照结构变化显示未同步（预期，需运营重新发布）。

## 开放问题

无。
