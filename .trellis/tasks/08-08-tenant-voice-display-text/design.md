# 设计：公司音色试听文本覆盖

## 数据模型

将错误实现的 `TenantTTSVoiceDisplayText` 替换为 `TenantTTSVoiceTestText`：

- `tenant`: 公司外键，使用现有租户隔离管理器；
- `voice`: TTS 音色外键；
- `test_text`: 1–2000 字符，保存规范化后的非空文本；
- `(tenant, voice)` 唯一约束；
- 删除公司或音色时级联删除。

迁移只创建空表，不回填。公司没有记录时自然回退供应商默认试听文本。

## 后端边界

`_build_company_tts_options_payload` 只在认证 Web 请求中查询当前租户、当前有效音色的覆盖映射，并将映射传入 `CompanyTTSVoiceSerializer` context。serializer 为 Web options 增加 `testText`（有效覆盖或平台回退）、`customTestText`（仅公司覆盖，无覆盖为空字符串）、`platformTestText`、`hasTestTextOverride`；设备码请求不传 context，保留原有 voice 字段集合和值。

覆盖资源 view 使用 `ensure_tts_voice_authorized_for_tenant` 做统一授权，再执行 `update_or_create` 或删除。租户从 `request_tenant` 获取，不接受 tenantId。

`CompanyTTSTestView` 在显式 text 为空时，按已解析的授权 voice 查找当前租户覆盖；有覆盖则使用覆盖，否则使用 adapter 的供应商默认文本。显式 text 优先。覆盖只进入 HTTP 测试播放，不进入 `TTSRuntimeView`、实时 TTS 或设备配置。

## HTTP 契约

```text
PUT    /api/v1/ai-models/tts/voice-test-texts/{voiceId}/
       {"testText": "公司专属试听内容"}
DELETE /api/v1/ai-models/tts/voice-test-texts/{voiceId}/
GET    /api/v1/ai-models/tts/options/
POST   /api/v1/ai-models/tts/test/
```

PUT 返回更新后的 company voice record；DELETE 返回 `204`。文本校验在 serializer 入口完成，首尾空白不计入长度。

## 前端

`TtsVoiceRecord` 增加试听文本字段。页面继续让用户临时编辑测试输入，但增加每音色“编辑试听文本”弹窗：保存调用 PUT，恢复平台默认调用 DELETE；options 刷新后同步 `testText`。选择音色变化时，输入框设置为该音色有效试听文本，避免沿用另一音色的文本。

沿用现有 Tabler 图标、流体文字和响应式卡片样式；不新增业务 WebSocket。

## 风险与回滚

错误的 display-name 实现、路由、测试和 0058 migration 必须从工作树移除；不保留别名或兼容端点。正确实现使用新的 0058 migration 名称和模型，旧的 display-name 表不会进入数据库。回滚时删除应用代码后回滚试听文本迁移，不触碰既有 TTS 配置数据。

GitNexus impact 结果若因索引不可用返回 UNKNOWN，只记录该事实，不伪造低风险结论；源码和目标测试仍是实施依据。
