# 确定动态表单项定位与聚焦实现

Type: prototype
Status: resolved

## Question

在 antd `Form.List` 中，如何以最小改动使顶部固定的“新增文本”入口在追加或向上插入后，可靠地将独立条目列表滚动到目标卡片，并将焦点置于目标条目的中文输入框，同时兼顾动态渲染和移动端？

## Answer

采用单一的新增/插入辅助流程：调用 `add()` 前记录目标表单索引，使用 ref 将对应条目卡片与中文 `TextArea` 注册到映射中；待 React 完成动态渲染后，在 effect 中调用目标卡片的 `scrollIntoView({ block: 'nearest' })`，再调用目标 `TextArea` 的 `focus()`。

“新增文本”按钮保留在内容区顶部，并通过 `position: sticky` 固定在条目列表滚动容器顶部。将条目卡片放入具有响应式 `max-height` 和 `overflow-y: auto` 的独立区域，使长表单只滚动条目列表，按钮与国际化方案选择始终可见。移动端使用同一容器和 `max-height`，不设置固定像素宽度。

“向上插入”复用同一辅助流程，目标索引为插入位置；追加时目标索引为新增前的条目数量。删除不触发自动定位。
