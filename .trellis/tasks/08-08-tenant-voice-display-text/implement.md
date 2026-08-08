# 实现清单：公司音色展示文本覆盖

## 实施顺序

1. 实施前重试 GitNexus 对 `CompanyTTSVoiceSerializer`、`_build_company_tts_options_payload` 与 `CompanyTTSOptionsView` 的 impact 分析；若风险为 HIGH 或 CRITICAL，先向用户报告影响面。
2. 在 `backend/apps/ai_models/models.py` 新增 `TenantTTSVoiceDisplayText` 与唯一约束，生成仅建表的迁移。
3. 在 `backend/apps/ai_models/serializers.py` 为公司音色 serializer 增加有效名称、平台默认名称和覆盖状态的序列化投影；平台 serializer 不改语义。
4. 在 `backend/apps/ai_models/views.py` 的公司 options 构建边界预取覆盖映射；仅认证 Web 请求应用映射。实现经授权校验的覆盖资源 `PUT` 与 `DELETE`，不触发运行时配置通知。
5. 在 `backend/apps/ai_models/urls.py` 注册复数资源路径。
6. 更新 `web/src/api/modules/tts.ts` 的类型与请求函数；更新 `web/src/views/tts-management/index.tsx` 的逐音色编辑与恢复默认交互。设备管理页继续消费有效 `displayName`，不新增第二套逻辑。
7. 为 options 回退、双租户隔离、授权拒绝、保存、清空、设备码保持全局名称补充 Django API 测试。

## 验证

1. `docker compose exec backend python manage.py test apps.ai_models.tests.test_company_tts_options_api --keepdb`
2. 如迁移或授权共用测试受影响，执行 `docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_authorization apps.ai_models.tests.test_company_tts_options_api --keepdb`
3. 在 `web/` 执行 `npm run build`。
4. 手动确认：同一音色在两个公司显示不同文本；清空后恢复超管名；设备管理页随公司 Web options 显示有效名称；设备码 options 仍为全局名称。
5. 提交前运行 GitNexus `detect_changes`，确认只波及预期 TTS options 与公司管理页面流程。

## 高风险文件与回滚点

| 文件 | 风险 | 回滚点 |
| --- | --- | --- |
| `backend/apps/ai_models/models.py` 与迁移 | 租户隔离和唯一性 | 新表独立，可先回滚应用再回滚迁移 |
| `backend/apps/ai_models/serializers.py` | 公司与平台 payload 不可混淆 | 只修改公司 serializer，平台 serializer 保持原样 |
| `backend/apps/ai_models/views.py` | options 同时供 Web 与设备码读取 | 以请求类别明确限制覆盖映射 |
| `web/src/views/tts-management/index.tsx` | 多个管理入口名称一致性 | 只写入 API，有效名称仍统一来自 options |
