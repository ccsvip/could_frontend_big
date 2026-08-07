# Design — CosyVoice 音色编辑与头像上传

## Architecture

```
[CosyVoiceSettingsPage]
  ├─ 服务配置 Card（现有 Form + PATCH /settings/tts/cosyvoice/）
  └─ 音色卡片墙
       ├─ 卡片：头像预览 / 更换头像 / 试听 / 编辑 / 删除
       ├─ EditVoiceModal → PATCH JSON
       └─ ChangeAvatarModal → PATCH multipart (avatar file)
```

## Backend

### Endpoint（保持路径，扩展契约）

`PATCH /api/v1/settings/tts/cosyvoice/voices/{voice_id}/`

- 权限：`IsSuperUser`（不变）
- Content-Type：
  - `application/json`：`displayName` / `isActive` / `isVisible` / `isDefault` / 可选 `avatarPath` 字符串（兼容）
  - `multipart/form-data`：同上字段 + 可选文件字段 `avatar`

### 文件处理

1. 校验：content-type 或扩展名为 image/jpeg、image/png、image/webp（无文件大小上限）

2. 使用 `default_storage.save('tts/voice-avatars/{voice_id}/{uuid}{ext}', ContentFile)`
3. 将 `voice.avatar_path` 设为 **以 `/` 开头的可服务路径**（优先 `settings.MEDIA_URL + name` 规范化后的 path，如 `/media/tts/voice-avatars/...`），以便现有 `get_avatarPath` 绝对化逻辑继续工作
4. 可选：覆盖上传时删除旧 **media** 路径文件（仅当旧 path 落在 voice-avatars 前缀下）；**不要删除** `/static/tts/voices/` 预设静态文件

### Serializer

- `CosyVoiceVoiceWriteSerializer` 增加可选 `avatar = ImageField(required=False)`（或 `FileField`）
- 视图中：若 `avatar` 存在则走存储逻辑写 `avatar_path`；其余字段映射逻辑保持

### 测试

- `test_tts_api.py` CosyVoice 相关类扩展：
  - multipart 上传 png → 201/200，响应 `avatarPath` 含 media 路径，DB `avatar_path` 更新
  - JSON 改 `displayName`/`isDefault` 仍通过
  - 非法类型/过大文件 400

## Frontend

### 页面结构（去掉 prototype 开关）

`web/src/views/cosyvoice-settings/index.tsx` 生产实现：

1. 保留服务配置 Card
2. 音色区改为 B 风格卡片网格
3. 弹窗：
   - 编辑：名称 + 启用 + 默认
   - 更换头像：当前缩略图（无路径）+ Upload.Dragger，仅本地文件
   - 头像 lightbox 预览
4. 复刻/设计 Modal 保留；创建可不带头像上传（创建后换）

### API module

`updateCosyVoiceVoice` 扩展：

- JSON 路径保持
- 若含 `avatar: File`，改 `FormData` multipart 提交（字段名 `avatar`，布尔/字符串字段一并 append）

### 组件拆分（正式代码，非 prototype）

建议同目录：

- `VoiceCardGrid.tsx` / 内联均可，保持 diff 可控
- `EditVoiceModal.tsx`
- `ChangeAvatarModal.tsx`
- `AvatarPreviewModal.tsx`

删除或停止引用：

- `prototype/*` 变体与 `PrototypeSwitcher` 在本页的挂载
- dev-only `?variant=` 分支

`components/prototype-switcher.tsx`：若无其它引用可保留文件或一并删除；本任务至少保证本页不引用。

## Compatibility

- 存量 `avatar_path` 静态路径继续可读
- 未上传头像的音色显示占位图标
- 不改 enroll/design 上游 CosyVoice API 契约

## Rollback

- 后端：去掉 multipart 分支不影响 JSON PATCH
- 前端：回退页面组件即可；已上传 media 文件可残留无害

## Trade-offs

| 方案 | 取舍 |
|------|------|
| 复用 `avatar_path` CharField + media 文件 | 无迁移，混静态/媒体路径需约定 |
| 新增 ImageField | 更「正统」但要迁移与双读逻辑 |
| 先上传资源库再写 URL | 用户已否决资源库路径 |

**采用**：CharField + media 存储。
