# 架构问题排查 Design

## Approach

本任务是架构评审，不是实现任务。排查以仓库事实为准：

1. 先使用领域词表和 ADR 建立不可推翻的业务语言与既有设计决策。
2. 再用 CodeGraph 查找高复杂度业务链路、跨层调用、重复接口和候选 Module。
3. 对每个候选问题读取真实源码，确认 Interface、Implementation、Seam、Adapter 和测试表面。
4. 用 deletion test 判断 Module 是 shallow 还是正在提供 depth。
5. 最后生成 OS temp 目录下的自包含 HTML 报告。

## Report Shape

报告文件写入 `%TEMP%\architecture-review-<timestamp>.html`。

每个候选卡片包含：

- Files
- Problem
- Solution
- Benefits / Wins
- Before / After diagram
- Recommendation strength: `Strong`、`Worth exploring` 或 `Speculative`
- ADR callout when applicable

报告末尾包含 Top recommendation，指出最值得先处理的候选。

## Evidence Rules

- CodeGraph 结果只能作为定位线索；最终候选必须通过源码阅读确认。
- 只提出有实际 friction 的候选，不列“理论上更优雅”的抽象。
- 与 ADR 冲突的候选必须保守处理，只在真实 friction 足够高时提出“重开 ADR”的可能。
- 不提出尚未被两个 Adapter 或真实变化点证明的虚假 Seam。

## Compatibility

本任务不改业务代码，因此无运行时兼容性风险。唯一仓库变更是 Trellis 规划文件。

## Rollback

若需要回滚本任务的仓库痕迹，只删除 `.trellis/tasks/07-18-architecture-review/` 中本次创建的规划文件和任务元数据即可。临时 HTML 报告位于 OS temp 目录，不影响仓库。
