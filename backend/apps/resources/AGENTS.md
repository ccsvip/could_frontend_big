[backend](../../AGENTS.md) > apps > **resources**

# apps/resources AGENTS.md

## OVERVIEW

最大的业务 app。承载图片/视频资源、滚动字幕、音色、3D 模型、**控制指令** 与 **点位**（point_* 子领域）。`views.py` 与 `serializers.py` 分别 ~30KB，是仓库里最复杂的两个 Python 文件之一。

## STRUCTURE

```
resources/
├── models.py             # Resource / VoiceTone / ModelAsset / ScrollingText / Command / CommandGroup ...
├── serializers.py        # 30KB，所有 DRF serializer
├── views.py              # 29KB，所有 viewset / api view
├── urls.py               # 路由：/resources/* + /commands/*
├── admin.py              # SimpleUI 后台（"资源（图片/视频）" 与 "模型管理" 分组）
├── tasks.py              # Celery 任务（缩略图、ASR 等）
├── point_models.py       # 点位（位置/坐标）模型
├── point_serializers.py
├── point_views.py        # /commands/points/
├── point_admin.py
├── point_runtime.py      # 点位运行时计算
├── migrations/           # 24 个迁移
└── tests/                # 16 个 test 文件
```

## CONVENTIONS

- **子领域分文件**：`point_*` 一组文件 = 控制点位子领域（不拆 app）；新增子领域**也**遵循同样的 `<domain>_<role>.py` 模式而不是再开 app，除非真的独立。
- **资源类型分两路**：图片/视频共用 `Resource(resource_type=...)` 一张表；3D 模型 `ModelAsset` 与音色 `VoiceTone` 是独立模型。Django admin 要明确分组：「资源（图片/视频）」「模型管理」「音色管理」。
- **本地地址生成**：`ModelAsset.local_url` / `effective_url` 由 `views.py` 在序列化时**运行时**生成（基于 `model_file` 与请求 host），不存库、不可写。
- **音色字段**：`voice_code` 是业务对外稳定 ID（前端 `voiceCode`），可编辑但全局唯一；`name` 仅展示。
- **测试组织**：每个独立功能一个 `test_<feature>.py`（如 `test_voice_tone_api.py` / `test_model_asset_api.py` / `test_admin_model_asset.py`）。

## ANTI-PATTERNS

- ❌ 在 admin 中把"模型管理"和"资源（图片/视频）"放进同一 ModelAdmin：用户在后台会串页（已修复，要回归测试 `test_admin_model_asset.py`）。
- ❌ 让 `local_url` 进 `serializer.Meta.fields` 的可写字段：永远只读。
- ❌ 在 `views.py` 拼接绝对 URL 时假设 host 固定：用 `request.build_absolute_uri`。
- ❌ 把控制指令分类硬编码：分类来自 DB，前端会动态新增；新增分类成功响应必须把最新分类集合返回，否则前端筛选下拉要刷新。

## NOTES

- 控制指令导入/导出格式与前端 `web/src/views/command-management/command-export-format.ts` 严格一一对应；改字段两边都要改 + 写迁移测试。
- `tasks.py` 包含 ASR 异步任务，VoiceTone 上传后会触发；OperationalError 在调用处兜底，不阻断主流程。
- `views.py` 接近 700 行，看一眼 `urls.py` 先定位 endpoint 再翻 view 更高效。
- 知识库**不在**这个 app：在 `apps/knowledge_base/`（独立 app），不要回填到这里。
