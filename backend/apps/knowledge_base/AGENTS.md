[backend](../../AGENTS.md) > apps > **knowledge_base**

# apps/knowledge_base AGENTS.md

## OVERVIEW

知识库文档上传、列表、下载、批量 ZIP 下载。文档上传即进入知识库，不存在审核/处理状态流程。

## STRUCTURE

```
knowledge_base/
├── models.py          # KnowledgeDocument + 文件元数据自动填充
├── serializers.py     # 上传/列表/详情 payload
├── views.py           # list/retrieve/create/destroy/download/bulk-download
├── services.py        # 飞书通知（复用 resources.services.feishu）
├── admin.py           # 知识库与文档后台维护
├── urls.py            # /knowledge-base/*
└── tests/             # API / access_data / helpers
```

## WHERE TO LOOK

| 任务 | 位置 | 注意 |
|------|------|------|
| 改文档字段 | `models.py` + `serializers.py` + `admin.py` | `save()` 会从 file 自动回填元数据 |
| 改列表/上传 | `views.py:KnowledgeDocumentViewSet` | 继承 `CachedBusinessResponseMixin` |
| 改单文件下载 | `views.py:download` | 返回 `FileResponse`，不是 JSON envelope |
| 改批量下载 | `views.py:bulk_download` | ZIP 临时文件 + 限制 20 个 / 200MB |
| 改通知 | `services.py` | 跨 app 复用 `resources.services.feishu.notify_business_event` |

## CONVENTIONS

- **无审核状态**：知识库文档上传即保存并参与检索，不再维护 `processing_status` / `processing_result`。
- **二进制响应例外**：`download` 和 `bulk_download` 成功时返回原生文件响应；错误仍走 DRF validation/envelope。
- **下载计数原子递增**：用 `F('download_count') + 1`，不要读改写。
- **删除要清文件**：`perform_destroy()` 先删 DB，再删除 storage 文件，避免孤儿文件。
- **批量下载限制**：有效文件最多 20 个，总大小最多 200MB；非法/重复/无文件 id 会被过滤。
- **ZIP 临时文件清理**：临时 zip 通过 `response._resource_closers` 注册清理，改动时必须保留释放路径。

## ANTI-PATTERNS

- ❌ 恢复文档审核/处理状态：当前产品契约是上传即进入知识库。
- ❌ 把下载成功响应包装成 `{status,message,data}`：前端下载 helper 需要真实 Blob/ZIP。
- ❌ 批量下载不去重 id：会重复写 zip entry / 重复计数。
- ❌ 覆盖 `perform_destroy()` 但忘记删除 `file_field`：会留下媒体孤儿文件。
- ❌ 绕过 `CachedBusinessResponseMixin` 直接 `cache.set()`：会破坏命名空间清理。
- ❌ 多租户改造后继续使用 `knowledge-base/%Y/%m/%d` 全局路径：文件 URL 可能跨租户可猜。

## NOTES

- 文件名去重由 `build_zip_entry_name()` 做 `name(1).ext` 形式。
- `build_content_disposition()` 使用 RFC 5987 `filename*=UTF-8''...`，不要退回裸中文 filename。
- `uploaded_by` 只是上传人，不等同租户边界；多租户时仍要加 `tenant` 字段和下载二次校验。
