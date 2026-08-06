# Implement: 智能体联网搜索开关

## Checklist

### 1. Backend model + migration

- [x] `AgentApplication.enable_web_search = BooleanField(default=False)`
- [x] Migration: AddField + RunPython 按 `llm_model.enable_web_search` 回填存量
- [x] `build_publish_config` / `runtime_config` 增加 `enable_web_search`

### 2. Serializer + API tests

- [x] `AgentApplicationSerializer` 增加 `enableWebSearch`
- [x] `test_agent_application_api.py`：create/update/read；publish 快照含键
- [x] 缺键 `runtime_config` 回退单测

### 3. Request path AND

- [x] `views.py` chat send：application 存在时 AND 智能体开关
- [x] `realtime.py` `_prepare_device_llm_session`：AND runtime_config
- [x] 测试：智能体关 → payload 无 search；智能体开且模型开 → 有

### 4. Frontend

- [x] `applications.ts` / `llm-settings.ts` 类型
- [x] `application-management/index.tsx`：state、dirty、save、mismatch、编排 UI 块
- [x] 用 `llmOptions.enableWebSearch` 控制 disabled
- [x] 公司 options payload 暴露 `enableWebSearch`

### 5. Verify

- [x] 定向 Django 测试通过
- [x] `docker compose exec web npm run build` 通过

## Validation Commands

```bash
docker compose exec backend python manage.py makemigrations ai_models --name agentapplication_enable_web_search
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api apps.ai_models.tests.test_chat_api apps.ai_models.tests.test_llm_model_usage --keepdb
cd web && npm run build
```

## Risky Files

| 文件 | 风险 |
|------|------|
| `backend/apps/ai_models/models.py` | publish/runtime 漏键导致 is_published_current 永久 dirty 或运行时丢配置 |
| `backend/apps/ai_models/views.py` | 裸会话 AND 写错会关全站 chat 联网 |
| `backend/config/realtime.py` | 设备语音路径 |
| `web/src/views/application-management/index.tsx` | 大文件，只改必要 state/UI |

## Rollback Points

1. 迁移后 API 未通：回滚 migration
2. 仅前端：隐藏开关即可，字段保留
3. 运行时误关联网：热修 realtime/views 临时 `or True` 仅模型（不推荐上生产，仅紧急）

## Out of implement scope

- 改 settings-llm 文案
- 改 forced_search 策略
- 会话级开关
