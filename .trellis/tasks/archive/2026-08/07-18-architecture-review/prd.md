# 架构问题排查

## Goal

排查当前 Solin 数字人管理平台的架构问题，输出一份有代码证据、领域语境和优先级的架构评审报告，帮助后续选择最值得推进的重构方向。

本任务只做架构排查和报告交付，不直接修改业务代码。

## Confirmed Facts

- 项目是单仓库，包含后端 Django 服务、前端 React/TypeScript 管理端，以及 Docker Compose 开发环境。
- 项目要求优先使用 CodeGraph 理解结构和调用关系，再降级到源码搜索与阅读。
- 项目领域词表在 `CONTEXT.md`，主要业务概念包括 Device Runtime、Agent Application、Agent Runtime Backend、Third-Party Chatbot、Provider Voice、Device TTS Voice Configuration、Company ASR Ignored Transcript Set、Control Command 等。
- 现有 ADR 已固定若干设计决策：
  - Agent Annotation 变更属于 Agent Application 发布边界。
  - Knowledge Media Asset 通过 Resource Library Item 与 Knowledge Base 绑定，不嵌入原始 URL。
  - Third-Party Chatbot 是独立的 Agent Runtime Backend，不是 OpenAI 兼容模型提供商。
  - Third-Party Chatbot Scheme Instance 存储 API flow snapshot。
  - Device Agent ASR runtime settings 使用 company-scoped override。
- 架构报告必须使用 `improve-codebase-architecture` 技能的术语：Module、Interface、Implementation、Depth、Seam、Adapter、Leverage、Locality。

## Requirements

- R1. 报告必须基于真实仓库证据，而不是只按目录结构或主观印象判断。
- R2. 排查范围覆盖后端、前端、跨层契约和运行时链路，重点关注当前领域复杂度最高的区域。
- R3. 每个候选架构问题必须包含涉及文件、问题、建议、收益和推荐强度。
- R4. 每个候选必须说明当前 Module 是否 shallow、Interface 如何泄漏复杂度、Deepening 后如何提升 locality 和 leverage。
- R5. 如果建议与现有 ADR 有冲突，报告必须明确标记，并说明是否真的值得重开该 ADR。
- R6. 报告必须以临时 HTML 文件交付到 OS temp 目录，不把报告文件写入仓库。
- R7. 本任务不做业务代码修改、不新增接口、不变更测试；只输出可供后续选择的架构候选。

## Acceptance Criteria

- [ ] 已读取 `CONTEXT.md`、相关 ADR、架构评审技能术语和 HTML 报告模板。
- [ ] 已使用 CodeGraph 或等价图谱能力定位主要结构、调用路径或热点模块。
- [ ] 已阅读每个候选问题涉及的真实源码，报告中的文件引用可追溯。
- [ ] HTML 报告包含至少 3 个架构候选问题，每个候选有 before/after 可视化。
- [ ] 每个候选使用 Module / Interface / Implementation / Depth / Seam / Adapter / Leverage / Locality 术语描述。
- [ ] 报告包含 Top recommendation，并说明优先处理理由。
- [ ] 最终回复提供报告绝对路径和最高优先级结论。

## Out Of Scope

- 不直接实施重构。
- 不修改生产配置、数据库迁移、前端页面或后端接口。
- 不创建 ADR，除非后续用户选择某个候选并要求记录决策。
- 不把临时 HTML 报告纳入 Git。
