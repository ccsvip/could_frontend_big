# Implement — CosyVoice 音色编辑与头像上传

## Checklist

1. **Backend write path**
   - [x] `CosyVoiceVoiceWriteSerializer` 支持可选 `avatar` 文件
   - [x] `CosyVoiceVoiceDetailView.patch` 处理 multipart：存文件 → 写 `avatar_path`；保留 JSON 字段更新与默认音色逻辑
   - [x] 类型/大小校验与明确 400 错误
   - [x] `CosyVoiceEnrollSerializer` 可选 `avatar = ImageField`
   - [x] `CosyVoiceEnrollView`：MultiPart/Form/JSON parsers；enroll 成功后可选 `store_cosyvoice_voice_avatar`

2. **Backend tests**
   - [x] 扩展 CosyVoice voice detail 测试：上传头像、编辑字段、非法文件
   - [x] `test_enroll_with_avatar_multipart_persists_media_path`：multipart enroll + avatar → 201，avatarPath 含 media 与 voice id
   - [x] `test_enroll_with_invalid_avatar_rejects_before_create`：非法头像在创建上游/本地音色前 400
   - [x] `docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api.CosyVoiceApiTests --keepdb`

3. **Frontend API**
   - [x] `cosyvoice.ts`：`updateCosyVoiceVoice` 支持 `File` multipart
   - [x] `enrollCosyVoice`：有 `avatar` 时 FormData，否则 JSON

4. **Frontend page**
   - [x] 卡片墙列表 + 编辑/换头像/预览弹窗
   - [x] 保留服务配置与复刻/设计
   - [x] 复刻 Modal：可选 Upload.Dragger 本地头像 + 预览；开关弹窗重置 object URL
   - [x] 移除 prototype 分支与本页 switcher

5. **Cleanup**
   - [x] 删除 `web/src/views/cosyvoice-settings/prototype/`
   - [x] 删除 `components/prototype-switcher.tsx`（无其它引用）
   - [x] 定向校验：CosyVoiceApiTests + `npx tsc -b`

## Validation

```bash
# backend
docker compose exec -T backend python manage.py test apps.ai_models.tests.test_tts_api.CosyVoiceApiTests --keepdb -v2

# frontend
cd web && npx tsc -b --pretty false
```

## Risky files

- `backend/apps/ai_models/views.py` — CosyVoiceVoiceDetailView / CosyVoiceEnrollView
- `backend/apps/ai_models/serializers.py` — CosyVoiceVoiceWriteSerializer / CosyVoiceEnrollSerializer
- `backend/apps/ai_models/services/cosyvoice.py` — avatar storage helpers
- `web/src/views/cosyvoice-settings/index.tsx`
- `web/src/api/modules/cosyvoice.ts`

## Rollback points

- 后端 patch/enroll multipart 可独立回退；前端 UI 可独立回退
- 不依赖数据迁移（无 schema 变更）
