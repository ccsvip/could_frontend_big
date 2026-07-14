# 滚动文本查看长列表体验

Label: wayfinder:map

## Destination

确定滚动文本查看弹窗在条目很多时的可访问浏览方式，使管理用户能明确看到可继续浏览的内容并保持关键上下文可见。

## Notes

范围限定在滚动文本管理页面的“查看”Modal。沿用 antd、现有 Tailwind token 与响应式规范；不修改滚动文本数据、接口或编辑表单。

## Decisions so far

- [确定查看弹窗长列表滚动容器](issues/01-preview-scroll-container.md) - 标题与状态固定在容器外，文本列表按视口高度独立滚动，并始终显示纵向滚动条。
- [缩减查看文本列表高度](issues/02-reduce-preview-list-height.md) - 文本列表最大高度固定为当前可滚动区域的约 2/3；标题、状态和滚动条策略保持不变。

## Not yet specified

<!-- 已无阻塞实现的交互决策。 -->

## Out of scope

- 滚动文本编辑表单的新增、插入、删除与排序交互。
- 滚动文本后端 API、模型、国际化字段与设备运行时展示。
- 以分页、虚拟列表或搜索替代查看弹窗的连续浏览。
