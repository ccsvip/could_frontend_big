# Implement — CosyVoice 音色编辑与头像上传

## Checklist

1. **Backend write path**
   - [x] `CosyVoiceVoiceWriteSerializer` 支持可选 `avatar` 文件
   - [x] `CosyVoiceVoiceDetailView.patch` 处理 multipart：存文件 → 写 `avatar_path`；保留 JSON 字段更新与默认音色逻辑
   - [x] 类型/大小校验与明确 400 错误

2. **Backend tests**
   - [x] 扩展 CosyVoice voice detail 测试：上传头像、编辑字段、非法文件
   - [x] `docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api.CosyVoiceApiTests --keepdb`

3. **Frontend API**
   - [x] `cosyvoice.ts`：`updateCosyVoiceVoice` 支持 `File` multipart

4. **Frontend page**
   - [x] 卡片墙列表 + 编辑/换头像/预览弹窗
   - [x] 保留服务配置与复刻/设计
   - [x] 移除 prototype 分支与本页 switcher

5. **Cleanup**
   - [x] 删除 `web/src/views/cosyvoice-settings/prototype/`
   - [x] 删除 `components/prototype-switcher.tsx`（无其它引用）
   - [x] `npm run build` 通过

## Validation

```bash
# backend
docker compose exec -T backend python manage.py test apps.ai_models.tests.test_tts_api.CosyVoiceApiTests --keepdb -v2
# -> Ran 14 tests OK (含 avatar multipart / json edit / invalid type)

# frontend
cd web && npm run build
# -> built successfully
```

## Risky files

- `backend/apps/ai_models/views.py` — CosyVoiceVoiceDetailView
- `backend/apps/ai_models/serializers.py` — CosyVoiceVoiceWriteSerializer
- `backend/apps/ai_models/services/cosyvoice.py` — avatar storage helpers
- `web/src/views/cosyvoice-settings/index.tsx`
- `web/src/api/modules/cosyvoice.ts`

## Rollback points

- 后端 patch 可独立回退；前端 UI 可独立回退
- 不依赖数据迁移（无 schema 变更）
