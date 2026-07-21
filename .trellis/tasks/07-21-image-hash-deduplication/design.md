# 图片 Hash 去重上传 - 技术设计

## Boundaries

- 仅处理 `Resource.resource_type=image`，视频与云端 URL 不参与。
- 去重键为 `(tenant, content_hash)`，摘要算法固定为 SHA-256。
- 前端负责在 R2 直传前计算摘要以节省重复上传流量；后端负责权限、租户范围、最终重复校验与并发约束。

## Data Model

- `Resource` 新增 `content_hash`，`CharField(max_length=64, blank=True, default='', editable=False)`。
- 增加条件唯一约束：仅当 `resource_type='image'` 且 `content_hash != ''` 时，`tenant + content_hash` 唯一。
- 历史记录默认空摘要，迁移不访问文件系统或对象存储。
- Serializer 使用 camelCase 字段 `contentHash`；响应可读，写入仅允许图片上传链路，必须校验为 64 位小写十六进制 SHA-256。

## Upload Flows

### Multipart Single Upload

1. 后端分块读取上传文件计算 SHA-256，并恢复文件流位置。
2. 在当前 tenant 图片集合内预检查重复；重复时返回可定位的 `duplicate_image` 冲突错误。
3. 保存时由数据库条件唯一约束处理并发竞态；冲突转换为相同错误。
4. 保存失败时清理本次产生的文件对象，避免孤儿文件。

### Multipart Batch Upload

1. 对请求内每个文件计算摘要，按文件顺序处理。
2. 请求内 Hash 重复或数据库已有 Hash 时跳过该文件，其余文件继续创建。
3. 响应改为 `{ created: ResourceRecord[], duplicates: [{ fileName, reason }] }`。
4. 前端成功提示分别展示新增数量与跳过数量，并列出重复文件名。

### R2 Direct Upload

1. 浏览器使用 Web Crypto `SHA-256` 计算文件摘要，同一批次先按摘要去重。
2. `POST /api/v1/resources/presign/` 对图片请求增加 `contentHash`；后端在签发 PUT URL 前按当前 tenant 检查重复，避免传输已存在内容。
3. 直传完成后创建图片资源时同时提交 `contentHash`。
4. 数据库唯一约束处理“签发后、创建前”的并发竞态；若最终创建发现重复，后端删除本次 tenant object key，前端将该项记为跳过并继续批次。

客户端摘要是 R2 直传的传输优化参数；安全边界仍由后端 tenant scope、对象键校验和数据库唯一约束建立。不会跨 tenant 查询或返回重复资源。

## Historical Backfill

- 新增可重复执行的 Django management command，扫描摘要为空的图片，按 `created_at, id` 顺序处理。
- 本地 `FileField` 使用分块读取；MinIO/R2 对象通过服务层流式读取，并确保响应连接关闭。
- 首个 Hash 记录保存为基准；若唯一约束表明已有基准，则保留当前资源摘要为空并输出重复报告。
- 缺失或无法读取的对象记录错误并继续，命令最终输出 indexed / duplicate / failed 统计，可再次执行。

## Error Contract

- 单图重复：HTTP `409 Conflict`，沿用全局错误 envelope，消息为“该图片已存在”。
- 批量上传通过 `duplicates` 返回文件名与原因；存在新增资源时返回 `201 Created`，整批均重复时返回 `200 OK`，均保持相同响应结构。
- 非法摘要：HTTP `400 Bad Request`，字段定位到 `contentHash`。

## Compatibility And Rollback

- 列表与现有资源响应只新增可选 `contentHash`，兼容现有调用者。
- 批量上传响应由数组变为对象，必须同步唯一前端调用点。
- 回滚前端不影响已记录摘要；回滚后端时可先移除唯一约束，再移除字段。
- 不在迁移中删除历史资源，不自动合并引用。

## Risks

- 浏览器 `file.arrayBuffer()` 会占用与图片大小相当的内存；图片现有上传规模可接受，不为本次引入增量哈希依赖。
- R2 直传内容无法由当前后端在上传前独立读取验证，服务端最终保证的是租户内声明摘要的唯一性；历史回填会基于真实对象字节重新计算。
- 对象上传成功但资源创建失败时必须清理新 object key，避免产生存储泄漏。
