# 滚动文本连续新增体验

Label: wayfinder:map

## Destination

确定并实现滚动文本编辑表单的连续新增与插入交互，使用户无需反复滚动即可继续录入新文本。

## Notes

范围限定在 `web/src/views/scrolling-text-management/index.tsx` 的编辑 Modal。沿用现有 antd、Tailwind token 和响应式规范；新增与向上插入必须遵循同一定位和聚焦规则。

## Decisions so far

- [确定动态表单项定位与聚焦实现](issues/01-form-list-focus-strategy.md) - 顶部入口 sticky 固定，条目列表独立滚动；追加和向上插入均滚至目标卡片并聚焦中文输入框。

## Not yet specified

<!-- 已无阻塞实现的交互决策。 -->

## Out of scope

- 后端滚动文本 API、数据模型和校验规则。
- 调整单条滚动文本的内容结构或国际化方案。
