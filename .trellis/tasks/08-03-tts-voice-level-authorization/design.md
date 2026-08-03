# Design — TTS 音色级授权与公司隔离

## 1. 架构边界

一句话：**授权推导仍然只有一个出口，本次只是把它的输入从「卡片」扩到「卡片 + 音色 + 归属」。**

```
超管授权页 ──PUT──> TenantTTSCardAuthorizationSerializer
                          │
                          ├─ TenantTTSProviderGrant  (卡片开关 + grant_mode + public_config)
                          └─ TenantTTSVoiceGrant     (音色勾选)   ← 新增
                          
公司选项 / 默认音色 / 试听 / 设备绑定 / HTTP runtime / 实时 WS
                          │  全部经由
                          ▼
      tts_authorization.get_effective_tts_voices_for_tenant()   ← 唯一改造点
                          │
                          ▼
      TTSVoice(is_active, is_visible, owner_tenant)             ← owner_tenant 新增
```

因为消费方早已全部收敛到 `tts_authorization`（见 prd 的「唯一入口」），本次不需要改任何消费方签名。这是本设计成立的前提，也是它风险可控的原因。

## 2. 数据模型

### 2.1 `TenantTTSProviderGrant` 新增 `grant_mode`

```python
GRANT_MODE_ALL = 'all'
GRANT_MODE_SELECTED = 'selected'
GRANT_MODE_CHOICES = [
    (GRANT_MODE_ALL, '全部音色'),
    (GRANT_MODE_SELECTED, '指定音色'),
]

grant_mode = models.CharField(
    '授权范围', max_length=16, choices=GRANT_MODE_CHOICES, default=GRANT_MODE_ALL,
)
```

`default='all'` 让迁移天然向后兼容：老 grant 行为不变，新建 grant 也默认「全部」。

### 2.2 新增 `TenantTTSVoiceGrant`

对齐 `TenantLLMModelGrant`（`models.py:100-125`）的形状，不发明新模式：

```python
class TenantTTSVoiceGrant(models.Model):
    tenant = FK('tenants.Tenant', related_name='tts_voice_grants')
    voice = FK(TTSVoice, related_name='tenant_grants')
    is_active = BooleanField(default=True)
    created_at / updated_at
    objects = TenantManager()

    class Meta:
        constraints = [UniqueConstraint(['tenant', 'voice'], name='uniq_tenant_tts_voice_grant')]
```

**为什么用 `is_active` 而不是「有行就是授权」**：与 `TenantTTSProviderGrant` / `TenantLLMModelGrant` 一致，保留「取消后重新勾选」的历史行，也让未来加审计字段（out of scope）时不需要改语义。

### 2.3 `TTSVoice` 新增 `owner_tenant`

```python
owner_tenant = models.ForeignKey(
    'tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True,
    related_name='owned_tts_voices', verbose_name='归属公司',
)
```

- `null` = 平台公有音色（存量全部如此）。
- `on_delete=CASCADE`：公司删除时其私有复刻音色一并删除。公有音色 `owner_tenant is None` 不受影响。
- **不加** `TenantManager()`：`TTSVoice` 是平台资源表，超管必须能看全集；租户过滤发生在 `tts_authorization` 内部，而不是 manager 层。这一点与 `TenantTTSProviderGrant` 有意不同，实现时不要顺手加上。

### 2.4 `is_visible` 只改标签

`verbose_name` 从「是否展示」改为「平台上架」。字段名、API 字段 `isVisible` 不动 —— 重命名会污染本次 diff 且改契约，收益只是可读性。

## 3. 授权推导（唯一核心改动）

`tts_authorization.get_effective_tts_voices_for_tenant`：

```python
queryset = (
    TTSVoice.objects
    .select_related('provider')
    .filter(
        is_active=True,
        is_visible=True,
        provider__is_active=True,
        provider__tenant_grants__tenant=tenant,
        provider__tenant_grants__is_active=True,
    )
    .filter(Q(owner_tenant__isnull=True) | Q(owner_tenant=tenant))          # R3
    .filter(                                                                 # R1
        Q(provider__tenant_grants__grant_mode=TenantTTSProviderGrant.GRANT_MODE_ALL)
        | Q(tenant_grants__tenant=tenant, tenant_grants__is_active=True)
    )
)
```

三条不变量，实现时必须守住：

1. **卡片开关优先**：卡片 grant `is_active=False` 时，无论音色 grant 如何都不可用。上面的写法天然满足 —— 卡片条件是 `AND`，音色条件只在其内部收窄。
2. **`grant_mode` 与卡片 grant 同一行**：两个 `provider__tenant_grants__` 条件放在同一个 `.filter()` 内才会作用于同一行 join。拆成两个 `.filter()` 会退化成「存在某行 active」+「存在某行 all」，公司有多卡时会串行。这是本次最容易写错的一处。
3. **`.distinct()` 必须保留**：多重反向 join 会放大行数，现有代码末尾已有 `.distinct()`，不要在重构中丢掉。

`_apply_model_code_filter`、排序、以及其余 8 个函数的签名与行为全部不变。`is_tts_voice_effective_for_tenant`、`ensure_tts_voice_authorized_for_tenant`、`resolve_device_tts_voice`、`resolve_realtime_tts_voice` 因为都建立在这一个 queryset 上，自动获得音色级 + 归属隔离，无需逐个改。

### 3.1 新增查询辅助

授权页与校验都需要「某音色是否即将失授权」，加一个：

```python
def tts_voice_grant_ids_for_tenant(tenant, provider) -> set[int]:
    """该公司在这张卡上已 active 勾选的音色 id 集合。"""
```

以及把 `tts_voice_usage_for_tenant` 的结果复用给 `canRevoke`，不新增第二套 usage 口径。

## 4. API 契约

### 4.1 GET `/settings/tts/tenants/<id>/card-authorizations/`

每张卡新增：

```
grantMode: 'all' | 'selected'
authorizedVoiceCount: number      # 当前模式下实际可用数
```

每个音色新增：

```
voiceGrantIsActive: boolean       # selected 模式下的勾选态
canRevoke: boolean                # false = 仍被引用，取消会 400
ownerTenant: { id, name } | null  # null = 平台公有
```

**过滤规则**：payload 中不包含 `owner_tenant` 为其他公司的音色。归属隔离在服务端完成，前端不做过滤 —— 与「不在页面层过滤」的原则一致。

### 4.2 PUT 同路径

```jsonc
{
  "cardGrants": [
    {
      "providerId": 1,
      "isActive": true,
      "grantMode": "selected",     // 可选，缺省 'all'（向后兼容旧客户端）
      "voiceIds": [12, 15],        // grantMode='selected' 时必填
      "publicConfig": { }          // 现有语义不变
    }
  ],
  "defaultVoiceId": 12
}
```

- `grantMode` 缺省为 `all` + `voiceIds` 缺省忽略 ⇒ 旧 payload 语义完全不变，前端可分批上线。
- `grantMode='all'` 时提交的 `voiceIds` 被忽略但**不清空**已有音色 grant，这样超管来回切换模式不会丢掉之前的勾选。

### 4.3 序列化器校验顺序

`TenantTTSCardAuthorizationSerializer.validate` 现有顺序是「归一化 grants → 校验默认音色 → 校验停用未被使用」。插入两步，保持先校验后写入：

1. 归一化时校验每个 `voiceIds` 元素：必须属于该 provider、必须 `owner_tenant in (None, tenant)`。跨公司私有音色 id 与不存在 id 报同一条文案，防探测（与 `ensure_tts_voice_authorized_for_tenant` 一致的策略）。
2. `_validate_default_voice`：把裸 `not voice.is_visible` 检查换成「按本次提交后的授权状态判断」。注意不能直接调 `is_tts_voice_effective_for_tenant`（那读的是**保存前**的库状态），必须基于 `normalized_grants` 推演本次提交后的可用集合。这是本次校验逻辑里第二个容易写错的地方。
3. 新增 `_validate_voice_revocation_not_in_use`：算出「保存后失授权集合」= 保存前可用 − 保存后可用，对其中每个音色查 `tts_voice_usage_for_tenant`，非空即 400。卡片整体停用仍走现有 `_validate_disable_not_in_use`，两者不重复报错（卡片级先判，命中即抛）。

### 4.4 写入

`put` 的事务内追加音色 grant 同步：

```python
for entry in grants:
    if entry['grantMode'] == 'selected':
        # 目标集合内 upsert is_active=True；该卡该公司其余音色 grant 置 is_active=False
```

只在 `selected` 模式下同步（见 4.2 的保留策略）。`publish_tenant_tts_config_changed` 保持在事务内、写入之后 —— 音色授权变化同样会改变在线设备的实际发音，这个通知不能漏。

## 5. CosyVoice 归属写入

`services/cosyvoice.py:_create_voice` 增加 `owner_tenant=None` 参数，透传到 `TTSVoice.objects.create`。`enroll_cosyvoice_voice` / `design_cosyvoice_voice` 同步加参数。

`CosyVoiceEnrollSerializer` / `CosyVoiceDesignSerializer` 增加可选 `ownerTenantId`：为空 = 平台公有；非空须是 active 公司。视图权限仍是 `IsSuperUser`，不开放公司自助。

`sort_order` 的计算 `TTSVoice.objects.filter(provider=...).count()`（`cosyvoice.py:204`）保持不变 —— 它是平台维度的排序基准，不应按公司分段。

## 6. 前端

`web/src/api/modules/tts.ts`：`TenantTtsCardAuthorization` 加 `grantMode` / `authorizedVoiceCount`，`TenantTtsCardAuthorizationVoice` 加 `voiceGrantIsActive` / `canRevoke` / `ownerTenant`；`TenantTtsCardGrantPayload` 加 `grantMode` / `voiceIds`。

`web/src/views/tts-card-authorization/index.tsx`：
- 卡片头部加「全部音色 / 指定音色」Segmented，头部计数改为「已授权 N / 共 M」。
- 音色行在 `selected` 模式下渲染 Checkbox；`canRevoke=false` 且当前已勾选时 disabled + Tooltip 说明引用位置。
- 删掉 line 185 的过期 Alert 文案。
- 私有音色行加归属公司 Tag。
- 本次**不做**脏态保护与分页（out of scope），但新增的 `grantMode` 切换同样只改本地 state、保存时统一 PUT，与现有 `toggleGrant` 风格一致。

`web/src/views/tts-settings/index.tsx:356`：列头「公司可见」→「平台上架」。

## 7. 迁移

三个迁移，拆开以便单独回滚：

| # | 内容 | 可逆 |
|---|---|---|
| 0049 | `TenantTTSProviderGrant.grant_mode` + `TenantTTSVoiceGrant` 建表 | 是 |
| 0050 | `TTSVoice.owner_tenant` 加列 | 是 |
| 0051 | `is_visible` verbose_name 变更（AlterField，无数据变更） | 是 |

**不需要数据回填迁移**：`grant_mode` 的 `default='all'` 与 `owner_tenant` 的 `null=True` 已经让存量数据落在「行为不变」的位置。这是相对 `0045_seed_tenant_tts_provider_grants.py` 的简化 —— 那次需要 seed 是因为当时 grant 表是空的，本次不是。

## 8. 兼容性与回滚

- **向后兼容**：旧前端不发 `grantMode` ⇒ 服务端按 `all` 处理 ⇒ 行为与今天一致。后端可先上线。
- **回滚**：回滚 0049/0050 会丢掉音色勾选与归属数据，但公司可用音色集合退回「卡片级全部」，不会出现「公司突然没音色」的可用性事故。
- **不可回滚的部分**：R2 删除的 `resolve_tts_voice` 死代码需要从 git 恢复，无数据影响。

## 9. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 多卡公司的 join 条件写错（§3 不变量 2） | 一张卡的 `all` 模式泄漏到另一张卡的 `selected` 模式 | 专门写「A 卡 all + B 卡 selected」的组合测试，断言两卡结果集互不影响 |
| 默认音色校验读了保存前状态（§4.3.2） | 超管一次提交里既取消勾选又设默认，校验放过 | 校验基于 `normalized_grants` 推演，测试覆盖「同一 PUT 内取消勾选 + 设为默认」 |
| `.distinct()` 在重构中丢失 | 授权页与公司选项出现重复音色 | 断言结果集长度的测试 |
| 归属过滤漏在某条路径 | 跨公司音色泄漏（本任务要修的正是这个） | 隔离测试覆盖全部 6 条消费路径，而不只是公司选项 |
