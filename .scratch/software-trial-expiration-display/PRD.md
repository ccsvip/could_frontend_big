# 软件试用标记与设备到期时间展示

Status: ready-for-agent

## Problem Statement

平台超级管理员在设备授权中心绑定或再次授权设备时，目前只能设置真实的设备授权类型和授权到期时间。设备管理页也只用一张“授权信息”卡片展示这组数据，无法分别表达“软件到期时间”和“大模型到期时间”。

产品需要新增一个独立的 Software Trial Indicator（软件试用标记），让软件到期时间可以仅在展示层选择“永久”或镜像真实的 Device Authorization Expiration（设备授权到期时间）。这个标记不能改变真实授权、设备过期判断、运行时访问控制、授权统计或筛选结果。同时，该字段需要在管理端接口、设备 HTTP 运行时配置和统一 WebSocket 完整配置中保持一致，以便所有展示端获得相同数据。

## Solution

在设备上持久化布尔字段 `isSoftwareTrial`，默认值为 `false`。超级管理员在“绑定设备”和“再次授权”弹窗中设置该字段；真实授权类型为“永久”时，软件试用标记必须关闭且不可启用，真实授权类型为“试用”时才允许选择。

设备管理页把原“授权信息”拆为“软件到期时间”和“大模型到期时间”两张独立卡片。大模型到期时间始终反映真实设备授权；软件到期时间仅根据 `isSoftwareTrial` 决定显示“永久”还是复用同一个 `expiresAt`。日期统一显示为 `YYYY-MM-DD`。

管理端设备响应、授权绑定/再次授权请求与响应、设备 HTTP 运行时配置以及统一 WebSocket 完整配置均传递 `isSoftwareTrial`。字段变化后，已订阅该设备运行时配置的在线客户端立即收到新的完整配置，而不是字段增量。真实授权逻辑继续只由 `authorizationType` 和 `expiresAt` 决定。

## User Stories

1. As an 平台超级管理员, I want 在绑定设备时看到“软件试用”开关, so that 我可以配置软件到期信息的展示方式。
2. As an 平台超级管理员, I want “软件试用”与现有“授权类型=试用”明确分离, so that 我不会把展示标记误认为真实授权。
3. As an 平台超级管理员, I want 新设备的软件试用开关默认关闭, so that 未显式选择软件试用时软件到期时间保持“永久”。
4. As an 平台超级管理员, I want 历史设备的软件试用标记在升级后默认为关闭, so that 发布此功能不会改变已有设备的展示和授权行为。
5. As an 平台超级管理员, I want 真实授权类型为“试用”时可以打开或关闭软件试用开关, so that 软件到期时间可以选择镜像真实授权日期或显示永久。
6. As an 平台超级管理员, I want 真实授权类型为“永久”时软件试用开关自动关闭并禁用, so that 不会产生没有可复用日期的矛盾状态。
7. As an 平台超级管理员, I want 从“试用”切换到“永久”时表单立即清除软件试用状态, so that 提交的数据符合永久授权规则。
8. As an 平台超级管理员, I want 真实授权类型为“试用”时仍必须选择到期时间, so that 现有真实授权校验不会被软件试用标记绕过。
9. As an 平台超级管理员, I want 再次授权设备时回显之前保存的软件试用状态, so that 我可以准确查看并修改当前配置。
10. As an 平台超级管理员, I want 绑定和再次授权使用同一个软件试用字段契约, so that 两种管理操作的行为保持一致。
11. As an 平台超级管理员, I want 授权中心列表不增加软件试用列, so that 授权中心继续专注于设置和维护授权，而不增加无关信息密度。
12. As an 设备管理用户, I want 看到独立的“软件到期时间”卡片, so that 我能直接识别软件展示的到期状态。
13. As an 设备管理用户, I want 看到独立的“大模型到期时间”卡片, so that 我能直接识别真实设备授权的到期状态。
14. As an 设备管理用户, I want 当真实授权为试用且软件试用关闭时看到“软件到期时间=永久”, so that 页面准确表达软件不按该日期展示到期。
15. As an 设备管理用户, I want 当真实授权为试用且软件试用开启时看到软件到期日期, so that 页面准确表达软件试用期限。
16. As an 设备管理用户, I want 试用设备的大模型到期时间始终显示真实授权日期, so that 软件展示标记不会掩盖真实授权期限。
17. As an 设备管理用户, I want 永久授权设备的两个到期时间都显示“永久”, so that 页面不会展示不存在的到期日期。
18. As an 设备管理用户, I want 到期日期统一显示为 `YYYY-MM-DD`, so that 页面不直接暴露难读的 ISO 时间或多余的时分秒。
19. As an 设备管理用户, I want “永久/试用”授权类型标签显示在“大模型到期时间”卡片上, so that 标签与真实授权概念保持一致。
20. As an 设备管理用户, I want 软件和大模型卡片的值只显示“永久”或日期, so that 卡片标题与内容不会重复。
21. As an 设备管理用户, I want 顶部试用/永久统计继续依据真实授权类型, so that 新展示标记不会改变现有业务统计口径。
22. As an 设备管理用户, I want 授权类型筛选继续依据真实授权类型, so that 软件试用标记不会让设备进入错误的筛选结果。
23. As an 管理端客户端, I want 设备列表和授权管理响应包含 `isSoftwareTrial`, so that 管理页面可以展示并回显该配置。
24. As an 设备运行时 HTTP 客户端, I want 在运行时配置的 `device` 对象中收到 `isSoftwareTrial`, so that 我可以使用与管理端一致的展示元数据。
25. As an 设备运行时 WebSocket 客户端, I want 在订阅成功的完整配置中收到 `isSoftwareTrial`, so that 初次连接即可得到完整展示状态。
26. As an 已在线的设备运行时客户端, I want 软件试用状态修改后立即收到新的完整配置, so that 我无需重连或再次发起 HTTP 请求即可刷新 UI。
27. As an 设备运行时客户端, I want 配置变化继续使用统一 WebSocket 入口和完整配置事件, so that 我不需要实现新的 WebSocket 地址或增量字段协议。
28. As an 设备使用者, I want 软件试用开关不影响设备是否被允许拉取配置或使用运行时能力, so that 纯展示设置不会意外停用设备。
29. As an 设备使用者, I want 真实试用授权到期后仍按现有规则被拒绝, so that 软件试用标记不能绕过真实授权。
30. As an 平台维护者, I want `isSoftwareTrial` 使用现有 camelCase API 约定, so that 新字段与其他设备字段保持一致。
31. As an 平台维护者, I want 新字段沿用现有设备序列化和完整运行时配置结构, so that HTTP 与 WebSocket 不会形成两套重复实现。
32. As an 平台维护者, I want 公司数据隔离和现有权限边界保持不变, so that 新展示字段不会扩大任何账号的数据访问范围。
33. As an 平台维护者, I want 不新增第二个到期日期字段, so that 软件到期展示始终复用唯一的真实授权日期并避免数据不一致。
34. As an 平台维护者, I want 不新增“一年”等期限快捷选项, so that 本次交付只解决已确认的展示与传输需求。

## Implementation Decisions

- 在 Device 数据模型上新增布尔持久化字段，数据库字段采用现有 snake_case 约定，API 字段固定为 `isSoftwareTrial`。
- 新字段数据库默认值为 `false`；迁移后的历史记录全部获得该默认值，不进行基于现有授权类型的推断或回填。
- Software Trial Indicator 是纯展示元数据。不得把它接入设备的真实过期属性、运行时设备校验、访问控制、启停状态或其他授权判断。
- Device Authorization Expiration 继续由现有 `authorizationType` 与 `expiresAt` 表达。试用授权仍要求 `expiresAt`，永久授权仍清空 `expiresAt`。
- 绑定和再次授权请求体在现有字段旁新增根级 `isSoftwareTrial: boolean`；未传值时按 `false` 处理。
- 后端必须执行与前端一致的约束：当 `authorizationType=permanent` 时，无论客户端提交什么值，最终持久化的 `isSoftwareTrial` 都必须为 `false`。
- 当 `authorizationType=trial` 时，持久化客户端提交的 `isSoftwareTrial`，并继续复用同一个 `expiresAt`。
- 绑定、再次授权、设备列表、设备详情和授权管理响应中的设备记录都以根字段返回 `isSoftwareTrial`。
- `GET /api/v1/device-runtime/config/` 在现有 `device` 对象内返回 `isSoftwareTrial`，不在响应顶层创建重复字段。
- WebSocket `device.runtime_config.subscribed` 在 `payload.config.device.isSoftwareTrial` 返回该值，与 HTTP 完整配置保持同源。
- 修改软件试用状态后，保留现有管理侧授权事件，并额外触发面向目标设备的运行时配置刷新，使已订阅客户端收到完整 `device.runtime_config.subscribed` 配置。
- 实时通知必须继续通过统一 WebSocket 入口和既有事件路由完成；不得新增业务 WebSocket URL，也不得只发送 `isSoftwareTrial` 增量。
- 授权中心的绑定和再次授权弹窗增加“软件试用”开关，位置在试用到期时间之后、设备启用开关之前。
- 新绑定表单默认 `isSoftwareTrial=false`；再次授权表单从设备记录回显该值。
- 真实授权类型为永久时，前端立即把开关设为关闭并禁用；后端同时兜底规范化为 `false`。
- 授权中心的设备请求、授权管理和日志列表均不新增软件试用展示列。
- 设备管理详情区把原“授权信息”卡片替换为“软件到期时间”卡片，并新增“大模型到期时间”卡片。
- 现有真实授权类型标签移动到“大模型到期时间”卡片；软件卡片不展示真实授权类型标签。
- 两张卡片的展示矩阵固定如下：

  | 真实授权类型 | `isSoftwareTrial` | 软件到期时间 | 大模型到期时间 |
  | --- | --- | --- | --- |
  | 永久 | `false`（强制） | 永久 | 永久 |
  | 试用 | `false` | 永久 | `expiresAt` |
  | 试用 | `true` | `expiresAt` | `expiresAt` |

- 日期仅在前端格式化为 `YYYY-MM-DD`；数据库与 API 继续保留完整、带时区的日期时间，真实授权判断不改变。
- 两张卡片的值只显示“永久”或格式化日期，不重复卡片标题文案。
- 设备统计中的试用/永久数量、授权类型筛选和真实授权标签继续只依据 `authorizationType`，不得读取 `isSoftwareTrial`。
- 继续沿用现有日期选择器，不新增一年、半年或永久等期限快捷控件。
- 前端改动沿用现有 antd、品牌 token、流体排版和响应式卡片网格，不引入新的图标库、硬编码主色或不符合规范的固定字体尺寸。
- 现有租户隔离、超级管理员权限、公司账号可见范围和 `X-Device-Code` 设备运行时认证方式全部保持不变。

## Testing Decisions

- 主要自动化测试缝使用现有设备授权 API 集成测试套件，从 HTTP 请求、数据库持久化和外部响应观察行为，不直接断言序列化器或内部辅助函数实现。
- 扩展现有“超级管理员绑定设备”测试：提交试用授权与 `isSoftwareTrial=true`，断言保存成功、响应根字段为 `true`、数据库记录为 `true`。
- 增加默认值测试：绑定请求省略 `isSoftwareTrial`，断言响应和持久化值均为 `false`；无显式值创建的历史兼容设备也应序列化为 `false`。
- 扩展现有“超级管理员再次授权”测试：验证 `true` 与 `false` 可以更新和回显，并验证切换为永久授权后最终值被强制规范化为 `false`。
- 扩展现有设备列表/授权管理 API 测试，断言设备记录根级包含 `isSoftwareTrial`，但不改变真实授权类型、统计和筛选结果。
- 扩展现有 HTTP 运行时配置测试，断言 `device.isSoftwareTrial` 与数据库值一致，同时保留现有完整配置字段。
- 扩展现有 `device.runtime_config.subscribe` WebSocket 集成测试，断言初始 `payload.config.device.isSoftwareTrial` 存在且值正确。
- 扩展现有运行时配置变化事件测试：再次授权修改软件试用状态后，目标设备订阅者收到新的完整配置；事件仍包含现有 application、agentApplication、wakeWords、voiceConfiguration 和 scrollingTexts 等完整片段，而不是单字段增量。
- 增加真实授权不受影响的回归测试：同一试用到期时间下，无论 `isSoftwareTrial` 为真或假，设备过期结果一致；永久授权不会因该标记被运行时拒绝。
- 测试继续使用现有租户测试基类和设备授权 API 先例，确保新字段不会绕过公司隔离。
- 前端必须通过现有 TypeScript/Vite 生产构建。仓库当前没有 React 组件测试框架，本需求不为两张展示卡片单独引入新的测试依赖。
- 前端人工验收按三行展示矩阵逐项执行，同时检查绑定默认值、永久授权禁用开关、再次授权回显、日期格式、授权标签位置、统计与筛选口径。
- 如实现者选择补充现有 Node 静态 UI 检查，应仅用于保护字段连线和关键文案，不得用静态源码匹配替代后端外部契约测试与人工展示验收。
- 后端验证优先在 Docker Compose 的 backend 容器中运行目标 Django 测试并使用 `--keepdb`；前端至少运行生产构建。

## Out of Scope

- 不改变真实设备授权、设备过期判断、运行时拒绝条件或授权安全策略。
- 不为“软件授权”建立第二套授权模型、单独的到期日期或独立许可证生命周期。
- 不解释或实现软件试用与非试用在产品能力上的其他差异。
- 不新增一年、半年、一个月等期限快捷选择。
- 不修改现有试用授权必须设置到期时间的校验。
- 不在授权中心列表或授权日志列表增加软件试用列。
- 不按 `isSoftwareTrial` 增加统计指标、筛选项、状态标签或权限规则。
- 不修改设备授权码资源及其授权类型语义。
- 不新增 REST API 路径、WebSocket URL 或单字段实时增量协议。
- 不重构设备管理页的其他卡片、资源绑定、唤醒词、音色或运行诊断功能。
- 不改变公司管理员与公司员工现有业务权限差异，也不改变平台管理员的 tenant scope 机制。

## Further Notes

- 领域词汇使用已确认的 Software Trial Indicator 与 Device Authorization Expiration；实现和文案应避免把软件试用标记称为真实授权类型。
- 本需求刻意复用唯一的 `expiresAt`，因此软件到期时间是派生展示值，不是独立业务日期。
- 该变更是局部、可逆的展示与契约扩展，不需要新增 ADR。
- 发布顺序应确保数据库迁移先于依赖新字段的应用代码生效，并保持旧记录默认值安全。
- 验收重点是“展示与传输发生变化，真实授权行为完全不变”。
