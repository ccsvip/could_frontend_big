# LLM Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build platform-managed LLM settings with shared platform API keys, per-company model authorization, company default models, configurable testing, and fail-closed model usage.

**Architecture:** Convert `LLMProvider` from tenant-owned configuration into a platform-owned provider catalog. Promote provider models from JSON strings to first-class `LLMModel` rows, then authorize effective models to tenants through tenant grant/settings tables. Company-facing APIs only expose effective enabled models and never expose API keys or API base URLs.

**Tech Stack:** Django 5.2 + DRF + SimpleJWT + httpx, React 18 + Vite + TypeScript + Antd 5, Docker Compose only for runtime/test commands.

---

## Confirmed Decisions

- Platform shares one API key per provider; companies do not own or see keys.
- Old tenant-scoped LLM provider configuration was never truly used and does not need compatibility.
- Global test prompt is shared by all model tests.
- Company side stores one company default LLM model.
- Model authorization is company-level only, not employee/role-level.
- Disabled or unauthorized provider/model must fail closed; no runtime fallback to another model.
- Test results are immediate only; no historical latency table.
- Super admin manages all provider/model/company authorization inside `设置 > LLM设置`.
- API keys are write-only after save; all responses use masking or an `apiKeyConfigured` boolean.
- New provider/model defaults to not authorized for any company.
- Global disable keeps authorization rows but makes models ineffective.
- Company and super admin test individual models, not provider defaults.
- Only company default model exists; no platform default model.
- Super admin and company users with update permission can set the company default model.
- Models become first-class rows with immutable real `name` after use and optional `displayName`.
- Used providers/models are not hard-deleted; they can only be disabled.
- System data is tenant-isolated; upstream provider account, billing, and provider-side logs are shared by platform key.
- Old chat/application LLM bindings are cleared/invalidated during migration.
- Company side does not display API base URL or API key.
- LLM setting/test operations enter audit logs without sensitive values.
- Test prompt is multiline, required, max 2000 chars.
- Test body text is not returned to company or super admin.
- Test cooldown/timeout/maxTokens are configurable in super admin LLM settings.
- Company default model changes affect only new records; new chats/apps snapshot the current default model into their records.
- Super admin authorization UI is company-centric.
- Company page groups effective models by provider.
- Menu/page label becomes `LLM设置`.
- Scope is LLM only; ASR/TTS are out of scope.

## File Structure

Backend:

- Modify `backend/apps/ai_models/models.py`
  - Convert `LLMProvider` to platform provider.
  - Add `LLMModel`, `TenantLLMModelGrant`, `TenantLLMSettings`, `LLMTestSettings`.
  - Change `AgentApplication` and `ChatConversation` to reference `LLMModel`.
- Create `backend/apps/ai_models/llm_services.py`
  - Effective model lookup, default model resolution, key masking, model test execution, usage checks.
- Modify `backend/apps/ai_models/serializers.py`
  - Platform serializers, company option serializers, chat/application serializers using `llmModelId`.
- Modify `backend/apps/ai_models/views.py`
  - Platform LLM settings endpoints, company LLM settings endpoints, chat/application model resolution.
- Modify `backend/apps/ai_models/urls.py`
  - Register new settings/company routes.
- Modify `backend/apps/ai_models/admin.py`
  - Admin display for platform provider/model/settings without exposing key values.
- Modify `backend/apps/accounts/permissions.py`
  - Reuse existing `ai_models.llm.*` permission classes and add platform settings permission mapping if needed.
- Modify/add migrations under `backend/apps/ai_models/migrations/`.
- Modify `backend/apps/audit/descriptions.py`
  - Add descriptions for new LLM settings endpoints.
- Add/modify tests:
  - `backend/apps/ai_models/tests/test_llm_platform_settings_api.py`
  - `backend/apps/ai_models/tests/test_llm_company_settings_api.py`
  - `backend/apps/ai_models/tests/test_llm_model_usage.py`
  - `backend/apps/ai_models/tests/test_chat_api.py`
  - `backend/apps/ai_models/tests/test_agent_application_api.py`
  - `backend/apps/tenants/tests/test_llm_isolation.py`
  - `backend/apps/tenants/tests/test_isolation_contract.py`

Frontend:

- Create `web/src/api/modules/llm-settings.ts`
  - Platform provider/model/settings/grant APIs.
  - Company options/default/test APIs.
- Modify `web/src/api/modules/chat.ts`
  - Replace `llmProviderId + modelName` payloads with `llmModelId`.
- Modify `web/src/api/modules/applications.ts`
  - Replace provider/model fields with `llmModelId` fields.
- Create `web/src/views/llm-settings/index.tsx`
  - Shared company-facing page or new company-specific page for effective models/default/testing.
- Create/modify `web/src/views/settings-llm/index.tsx`
  - Super admin platform settings page.
- Modify `web/src/views/llm-management/index.tsx`
  - Either replace with a wrapper/export to `llm-settings`, or retire CRUD behavior.
- Modify `web/src/router/index.tsx`
  - Add `/settings/llm`.
  - Keep company `/ai-models/llm` pointed at the company LLM settings page.
- Modify `web/src/layouts/dashboard-layout.tsx`
  - Add `LLM设置` under super admin settings.
  - Rename company `LLM管理` to `LLM设置`.
- Modify `web/src/views/chat-room/index.tsx`
  - Use authorized LLM model options and `llmModelId`.
- Modify `web/src/views/application-management/index.tsx`
  - Use authorized LLM model options and `llmModelId`.
- Add static frontend checks:
  - `web/scripts/test-llm-settings-static.mjs`

## Task 0: Prepare Execution Branch

**Files:**
- No code files.

- [ ] **Step 1: Inspect branch and working tree**

Run:

```bash
git status --short
git branch --show-current
```

Expected: note any user-owned changes. Do not revert unrelated files.

- [ ] **Step 2: Create dev branch from main**

Run:

```bash
git switch main
git pull --ff-only
git switch -c dev/llm-settings
```

Expected: new branch `dev/llm-settings`.

## Task 1: Add Backend LLM Domain Tests First

**Files:**
- Create: `backend/apps/ai_models/tests/test_llm_platform_settings_api.py`
- Create: `backend/apps/ai_models/tests/test_llm_company_settings_api.py`
- Create: `backend/apps/ai_models/tests/test_llm_model_usage.py`
- Modify: `backend/apps/tenants/tests/test_llm_isolation.py`

- [ ] **Step 1: Add platform settings tests**

Create tests that assert:

```python
def test_superuser_can_create_platform_provider_without_returning_raw_key(self):
    self.client.force_authenticate(self.superuser)
    resp = self.client.post('/api/v1/settings/llm/providers/', {
        'name': 'OpenAI Platform',
        'providerType': 'openai',
        'apiBaseUrl': 'https://api.openai.com/v1',
        'apiKey': 'sk-secret',
        'isActive': True,
    }, format='json')
    self.assertEqual(resp.status_code, 201)
    self.assertEqual(resp.data['name'], 'OpenAI Platform')
    self.assertNotIn('sk-secret', str(resp.data))
    self.assertTrue(resp.data['apiKeyConfigured'])
    self.assertTrue(resp.data['apiKeyMasked'].startswith('sk-'))
```

Add tests for:
- non-superuser cannot call `/settings/llm/providers/`.
- model creation under provider.
- used model real `name` cannot be changed.
- used provider/model cannot be hard-deleted.
- global test settings validation rejects empty prompt, prompt > 2000 chars, timeout outside 1-60, maxTokens outside 1-512.

- [ ] **Step 2: Add company settings tests**

Create tests that assert:

```python
def test_company_only_sees_effective_authorized_models_without_secrets(self):
    self.client.force_authenticate(self.tenant_user)
    resp = self.client.get('/api/v1/ai-models/llm/options/')
    self.assertEqual(resp.status_code, 200)
    self.assertNotIn('apiKey', str(resp.data))
    self.assertNotIn('apiBaseUrl', str(resp.data))
    self.assertEqual(resp.data['providers'][0]['models'][0]['id'], self.model.id)
```

Add tests for:
- unauthorized models are invisible.
- provider disabled makes authorized model invisible.
- model disabled makes grant ineffective.
- company can set default only to effective model.
- user with `ai_models.llm.view` can test but cannot set default.
- user with `ai_models.llm.update` can set default.
- test cooldown is enforced and configurable.

- [ ] **Step 3: Add model usage tests**

Create tests that assert:

```python
def test_chat_creation_snapshots_company_default_model(self):
    self.client.force_authenticate(self.tenant_user)
    resp = self.client.post('/api/v1/ai-models/chat/conversations/', {'title': '新对话'}, format='json')
    self.assertEqual(resp.status_code, 201)
    conversation = ChatConversation.objects.get(id=resp.data['id'])
    self.assertEqual(conversation.llm_model_id, self.default_model.id)
```

Add tests for:
- no explicit model and no company default returns 400.
- update chat config rejects unauthorized model.
- send rejects disabled/unauthorized bound model and does not fallback.
- application creation snapshots company default model.
- application model selection rejects unauthorized model.

- [ ] **Step 4: Run failing tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_platform_settings_api apps.ai_models.tests.test_llm_company_settings_api apps.ai_models.tests.test_llm_model_usage apps.tenants.tests.test_llm_isolation
```

Expected: FAIL because new endpoints/models do not exist yet.

- [ ] **Step 5: Commit failing tests**

Run:

```bash
git add backend/apps/ai_models/tests/test_llm_platform_settings_api.py backend/apps/ai_models/tests/test_llm_company_settings_api.py backend/apps/ai_models/tests/test_llm_model_usage.py backend/apps/tenants/tests/test_llm_isolation.py
git commit -m "test: 覆盖平台LLM设置与公司授权行为"
```

## Task 2: Implement Backend Models and Migration

**Files:**
- Modify: `backend/apps/ai_models/models.py`
- Create: `backend/apps/ai_models/migrations/00xx_platform_llm_settings.py`
- Modify: `backend/apps/tenants/tests/test_isolation_contract.py`

- [ ] **Step 1: Update models**

Implement these model shapes in `backend/apps/ai_models/models.py`:

```python
class LLMProvider(models.Model):
    name = models.CharField('供应商名称', max_length=128)
    provider_type = models.CharField('供应商类型', max_length=32, choices=PROVIDER_TYPE_CHOICES, default='openai')
    api_base_url = models.URLField('API 地址', max_length=512)
    api_key = models.CharField('API 密钥', max_length=512)
    avatar = models.ImageField('供应商头像', upload_to='ai_models/avatars/', blank=True, null=True)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
```

```python
class LLMModel(models.Model):
    provider = models.ForeignKey(LLMProvider, on_delete=models.CASCADE, related_name='models', verbose_name='所属供应商')
    name = models.CharField('真实模型名称', max_length=128)
    display_name = models.CharField('展示名称', max_length=128, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.PositiveIntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'name'], name='uniq_llm_model_provider_name'),
        ]
```

```python
class TenantLLMModelGrant(models.Model):
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='llm_model_grants', verbose_name='所属公司')
    model = models.ForeignKey(LLMModel, on_delete=models.CASCADE, related_name='tenant_grants', verbose_name='授权模型')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'model'], name='uniq_tenant_llm_model_grant'),
        ]
```

```python
class TenantLLMSettings(models.Model):
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='llm_settings', verbose_name='所属公司')
    default_model = models.ForeignKey(LLMModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenant_default_settings', verbose_name='默认模型')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    objects = TenantManager()
```

```python
class LLMTestSettings(models.Model):
    test_prompt = models.TextField('测试提示词', default='请用一句中文回复：连接测试成功。')
    test_cooldown_seconds = models.PositiveIntegerField('测速冷却秒数', default=10)
    test_timeout_seconds = models.PositiveIntegerField('测速超时秒数', default=15)
    test_max_tokens = models.PositiveIntegerField('测速最大输出 Tokens', default=64)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
```

Change `AgentApplication` and `ChatConversation` to use:

```python
llm_model = models.ForeignKey(
    LLMModel,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='agent_applications',
    verbose_name='LLM 模型',
)
```

and:

```python
llm_model = models.ForeignKey(
    LLMModel,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='conversations',
    verbose_name='LLM 模型',
)
```

- [ ] **Step 2: Generate migration in container**

Run:

```bash
docker compose exec backend python manage.py makemigrations ai_models
```

Expected: a new migration is created under `backend/apps/ai_models/migrations/`.

- [ ] **Step 3: Edit migration data operation**

In the migration, add a `RunPython` data operation that:
- clears old `ChatConversation.llm_provider/model_name` bindings if those fields still exist before removal.
- clears old `AgentApplication.llm_provider/model_name` bindings if those fields still exist before removal.
- deletes old tenant-scoped `LLMProvider` rows or leaves them only if the migration has already removed the tenant field.

Use ORM inside migration only:

```python
def clear_old_llm_bindings(apps, schema_editor):
    ChatConversation = apps.get_model('ai_models', 'ChatConversation')
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    for model in (ChatConversation, AgentApplication):
        update_kwargs = {}
        field_names = {field.name for field in model._meta.fields}
        if 'llm_provider' in field_names:
            update_kwargs['llm_provider'] = None
        if 'model_name' in field_names:
            update_kwargs['model_name'] = ''
        if 'llm_model' in field_names:
            update_kwargs['llm_model'] = None
        if update_kwargs:
            model.objects.all().update(**update_kwargs)
```

- [ ] **Step 4: Update isolation contract exemptions**

`LLMProvider` must no longer have `tenant`, so it should not be in the tenant manager contract. `TenantLLMModelGrant` and `TenantLLMSettings` do have `tenant` and must use `TenantManager`.

- [ ] **Step 5: Run model migration checks**

Run:

```bash
docker compose exec backend python manage.py test apps.tenants.tests.test_isolation_contract
```

Expected: PASS after manager/exemption updates.

- [ ] **Step 6: Commit models and migration**

Run:

```bash
git add backend/apps/ai_models/models.py backend/apps/ai_models/migrations backend/apps/tenants/tests/test_isolation_contract.py
git commit -m "feat: 重构LLM平台模型与公司授权数据结构"
```

## Task 3: Add LLM Domain Services

**Files:**
- Create: `backend/apps/ai_models/llm_services.py`
- Modify: `backend/apps/ai_models/tests/test_llm_model_usage.py`

- [ ] **Step 1: Implement service API**

Create `llm_services.py` with functions:

```python
def mask_api_key(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '****'
    return f'{value[:3]}...{value[-4:]}'
```

```python
def get_effective_llm_models_for_tenant(tenant):
    if tenant is None:
        return LLMModel.objects.none()
    return (
        LLMModel.objects
        .select_related('provider')
        .filter(
            provider__is_active=True,
            is_active=True,
            tenant_grants__tenant=tenant,
            tenant_grants__is_active=True,
        )
        .order_by('provider__sort_order', 'provider__id', 'sort_order', 'id')
        .distinct()
    )
```

```python
def get_effective_llm_model_for_tenant(tenant, model_id):
    return get_effective_llm_models_for_tenant(tenant).filter(id=model_id).first()
```

```python
def get_tenant_llm_settings(tenant):
    settings, _ = TenantLLMSettings.objects.get_or_create(tenant=tenant)
    return settings
```

```python
def is_llm_model_effective_for_tenant(tenant, model) -> bool:
    if tenant is None or model is None:
        return False
    return get_effective_llm_models_for_tenant(tenant).filter(id=model.id).exists()
```

```python
def llm_model_has_usage(model) -> bool:
    return (
        model.tenant_grants.exists()
        or model.tenant_default_settings.exists()
        or model.conversations.exists()
        or model.agent_applications.exists()
    )
```

```python
def llm_provider_has_usage(provider) -> bool:
    return LLMModel.objects.filter(provider=provider).filter(
        models.Q(tenant_grants__isnull=False)
        | models.Q(tenant_default_settings__isnull=False)
        | models.Q(conversations__isnull=False)
        | models.Q(agent_applications__isnull=False)
    ).exists()
```

- [ ] **Step 2: Add test settings validator**

Add:

```python
def validate_llm_test_settings_values(*, prompt: str, cooldown: int, timeout: int, max_tokens: int) -> None:
    if not prompt.strip():
        raise ValidationError({'testPrompt': '测试提示词不能为空'})
    if len(prompt.strip()) > 2000:
        raise ValidationError({'testPrompt': '测试提示词不能超过 2000 字符'})
    if cooldown < 0 or cooldown > 3600:
        raise ValidationError({'testCooldownSeconds': '测速冷却时间必须在 0 到 3600 秒之间'})
    if timeout < 1 or timeout > 60:
        raise ValidationError({'testTimeoutSeconds': '测速超时时间必须在 1 到 60 秒之间'})
    if max_tokens < 1 or max_tokens > 512:
        raise ValidationError({'testMaxTokens': '测速最大输出 tokens 必须在 1 到 512 之间'})
```

- [ ] **Step 3: Run service-related tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_model_usage
```

Expected: tests still fail only on missing API/view integration, not import errors.

- [ ] **Step 4: Commit services**

Run:

```bash
git add backend/apps/ai_models/llm_services.py backend/apps/ai_models/tests/test_llm_model_usage.py
git commit -m "feat: 新增LLM有效模型与测试配置服务"
```

## Task 4: Implement Backend Serializers and Platform APIs

**Files:**
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/views.py`
- Modify: `backend/apps/ai_models/urls.py`
- Modify: `backend/apps/audit/descriptions.py`
- Test: `backend/apps/ai_models/tests/test_llm_platform_settings_api.py`

- [ ] **Step 1: Add platform serializers**

Add serializers:
- `PlatformLLMProviderSerializer`
- `PlatformLLMProviderWriteSerializer`
- `PlatformLLMModelSerializer`
- `PlatformLLMModelWriteSerializer`
- `LLMTestSettingsSerializer`
- `TenantLLMAuthorizationSerializer`

Provider response must include:

```python
fields = [
    'id', 'name', 'providerType', 'providerTypeLabel',
    'apiBaseUrl', 'apiKeyMasked', 'apiKeyConfigured',
    'avatar', 'avatarUrl', 'clearAvatar',
    'isActive', 'sortOrder', 'created_at', 'updated_at',
]
```

It must not include raw `apiKey`.

- [ ] **Step 2: Add model immutability validation**

In `PlatformLLMModelWriteSerializer.validate`, reject `name` changes when `llm_model_has_usage(instance)` is true:

```python
if self.instance and 'name' in attrs and attrs['name'] != self.instance.name:
    if llm_model_has_usage(self.instance):
        raise serializers.ValidationError({'name': '模型已被授权或使用，不能修改真实模型名称；请新增模型并停用旧模型'})
```

- [ ] **Step 3: Add platform viewsets/APIViews**

Add endpoints:

```text
GET/POST/PATCH/DELETE /api/v1/settings/llm/providers/
GET/POST/PATCH/DELETE /api/v1/settings/llm/models/
GET/PATCH /api/v1/settings/llm/test-settings/
GET/PUT /api/v1/settings/llm/tenants/<tenant_id>/authorization/
POST /api/v1/settings/llm/models/<model_id>/test/
```

All platform endpoints require `tenant.management.view` / superuser platform permission.

- [ ] **Step 4: Enforce delete guard**

Provider destroy:

```python
if llm_provider_has_usage(provider):
    raise ValidationError({'detail': '该厂商已被授权或使用，不能删除，请停用'})
```

Model destroy:

```python
if llm_model_has_usage(model):
    raise ValidationError({'detail': '该模型已被授权或使用，不能删除，请停用'})
```

- [ ] **Step 5: Implement company authorization update**

`PUT /settings/llm/tenants/<tenant_id>/authorization/` accepts:

```json
{
  "modelGrants": [{"modelId": 1, "isActive": true}],
  "defaultModelId": 1
}
```

Validate default model is in active grants and globally effective. Preserve inactive grant rows.

- [ ] **Step 6: Run platform tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_platform_settings_api
```

Expected: PASS.

- [ ] **Step 7: Commit platform APIs**

Run:

```bash
git add backend/apps/ai_models/serializers.py backend/apps/ai_models/views.py backend/apps/ai_models/urls.py backend/apps/audit/descriptions.py backend/apps/ai_models/tests/test_llm_platform_settings_api.py
git commit -m "feat: 增加平台LLM设置接口"
```

## Task 5: Implement Company LLM APIs and Testing

**Files:**
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/views.py`
- Modify: `backend/apps/ai_models/urls.py`
- Test: `backend/apps/ai_models/tests/test_llm_company_settings_api.py`

- [ ] **Step 1: Add company options endpoint**

Implement:

```text
GET /api/v1/ai-models/llm/options/
```

Response shape:

```json
{
  "defaultModelId": 1,
  "testSettings": {
    "testPrompt": "请用一句中文回复：连接测试成功。",
    "testCooldownSeconds": 10,
    "testTimeoutSeconds": 15,
    "testMaxTokens": 64
  },
  "providers": [
    {
      "id": 1,
      "name": "OpenAI Platform",
      "providerType": "openai",
      "providerTypeLabel": "OpenAI",
      "avatarUrl": "/media/...",
      "models": [
        {
          "id": 1,
          "name": "gpt-4o-mini",
          "displayName": "GPT-4o mini",
          "isDefault": true
        }
      ]
    }
  ]
}
```

Do not include `apiKey`, `apiBaseUrl`, disabled models, unauthorized models, or disabled providers.

- [ ] **Step 2: Add company default endpoint**

Implement:

```text
PATCH /api/v1/ai-models/llm/default-model/
```

Payload:

```json
{"modelId": 1}
```

Require `ai_models.llm.update`. Validate model is effective for request tenant.

- [ ] **Step 3: Add model test endpoint**

Implement:

```text
POST /api/v1/ai-models/llm/models/<model_id>/test/
```

Require `ai_models.llm.view`. Validate model is effective for request tenant. Use global test settings and return:

```json
{
  "success": true,
  "message": "连接成功",
  "latencyMs": 123,
  "testedAt": "2026-06-10T12:00:00+08:00"
}
```

Do not return completion content.

- [ ] **Step 4: Implement configurable cooldown**

Use Django cache key:

```python
cache_key = f'llm-test:{request.user.id}:{model.id}'
```

If `LLMTestSettings.test_cooldown_seconds > 0`, reject repeated tests before expiry.

- [ ] **Step 5: Run company tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_company_settings_api
```

Expected: PASS.

- [ ] **Step 6: Commit company APIs**

Run:

```bash
git add backend/apps/ai_models/serializers.py backend/apps/ai_models/views.py backend/apps/ai_models/urls.py backend/apps/ai_models/tests/test_llm_company_settings_api.py
git commit -m "feat: 增加公司LLM设置与测速接口"
```

## Task 6: Update Chat and Agent Application Model Binding

**Files:**
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/views.py`
- Test: `backend/apps/ai_models/tests/test_chat_api.py`
- Test: `backend/apps/ai_models/tests/test_agent_application_api.py`
- Test: `backend/apps/tenants/tests/test_llm_isolation.py`

- [ ] **Step 1: Replace chat config payload**

Change chat create/update config to accept:

```json
{"llmModelId": 1, "systemPrompt": "...", "temperature": 0.7, "maxTokens": 1000}
```

Keep response fields:

```json
{
  "llmModelId": 1,
  "llmModelName": "gpt-4o-mini",
  "llmModelDisplayName": "GPT-4o mini",
  "llmProviderName": "OpenAI Platform"
}
```

- [ ] **Step 2: Snapshot default model on create**

When creating a conversation without `llmModelId`:

```python
settings = get_tenant_llm_settings(tenant)
model = settings.default_model
if not is_llm_model_effective_for_tenant(tenant, model):
    raise ValidationError({'llmModelId': '请先选择模型或设置公司默认模型'})
```

Save `conversation.llm_model = model`.

- [ ] **Step 3: Remove runtime fallback**

In `send`, replace provider fallback with:

```python
model = conversation.llm_model
if not is_llm_model_effective_for_tenant(conversation.tenant, model):
    return Response({
        'status': 'error',
        'message': '该模型已被平台停用或未授权，请重新选择可用模型',
        'code': 400,
    }, status=status.HTTP_400_BAD_REQUEST)
```

Use `model.provider.api_key`, `model.provider.api_base_url`, and `model.name` for upstream calls.

- [ ] **Step 4: Update title generation**

Use the same `LLMModel` object as the conversation response model. Do not fallback to another model for title generation.

- [ ] **Step 5: Update application serializer**

Application create/update accepts `llmModelId`. If omitted, snapshot company default model exactly like chat create. Reject unauthorized model.

- [ ] **Step 6: Run behavior tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_chat_api apps.ai_models.tests.test_agent_application_api apps.tenants.tests.test_llm_isolation
```

Expected: PASS.

- [ ] **Step 7: Commit model binding changes**

Run:

```bash
git add backend/apps/ai_models/serializers.py backend/apps/ai_models/views.py backend/apps/ai_models/tests/test_chat_api.py backend/apps/ai_models/tests/test_agent_application_api.py backend/apps/tenants/tests/test_llm_isolation.py
git commit -m "feat: 聊天和应用改用授权LLM模型"
```

## Task 7: Add Frontend API Module

**Files:**
- Create: `web/src/api/modules/llm-settings.ts`
- Modify: `web/src/api/modules/chat.ts`
- Modify: `web/src/api/modules/applications.ts`

- [ ] **Step 1: Add TypeScript types**

Create types:

```ts
export type LLMModelOption = {
  id: number;
  name: string;
  displayName: string;
  isDefault: boolean;
};

export type LLMProviderOption = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  avatarUrl: string | null;
  models: LLMModelOption[];
};

export type LLMTestSettings = {
  testPrompt: string;
  testCooldownSeconds: number;
  testTimeoutSeconds: number;
  testMaxTokens: number;
};

export type CompanyLLMOptions = {
  defaultModelId: number | null;
  testSettings: LLMTestSettings;
  providers: LLMProviderOption[];
};
```

- [ ] **Step 2: Add company API functions**

Implement:

```ts
export const fetchCompanyLLMOptions = async () => {
  const response = await httpClient.get<CompanyLLMOptions>('/ai-models/llm/options/');
  return response.data;
};

export const updateCompanyDefaultLLMModel = async (modelId: number) => {
  const response = await httpClient.patch<CompanyLLMOptions>('/ai-models/llm/default-model/', { modelId });
  return response.data;
};

export const testCompanyLLMModel = async (modelId: number) => {
  const response = await httpClient.post<TestConnectionResult>(`/ai-models/llm/models/${modelId}/test/`);
  return response.data;
};
```

- [ ] **Step 3: Add platform API functions**

Implement functions for:
- `fetchPlatformLLMProviders`
- `createPlatformLLMProvider`
- `updatePlatformLLMProvider`
- `deletePlatformLLMProvider`
- `fetchPlatformLLMModels`
- `createPlatformLLMModel`
- `updatePlatformLLMModel`
- `deletePlatformLLMModel`
- `fetchPlatformLLMTestSettings`
- `updatePlatformLLMTestSettings`
- `fetchTenantLLMAuthorization`
- `updateTenantLLMAuthorization`
- `testPlatformLLMModel`

Use `/settings/llm/...` routes only.

- [ ] **Step 4: Update chat/application payload types**

Replace `llmProviderId` and `modelName` request payloads with `llmModelId`.

- [ ] **Step 5: Run TypeScript check**

Run:

```bash
docker compose exec web npm run build
```

Expected: FAIL until pages are updated.

- [ ] **Step 6: Commit API module**

Run:

```bash
git add web/src/api/modules/llm-settings.ts web/src/api/modules/chat.ts web/src/api/modules/applications.ts
git commit -m "feat: 新增LLM设置前端接口"
```

## Task 8: Build Super Admin LLM Settings Page

**Files:**
- Create: `web/src/views/settings-llm/index.tsx`
- Modify: `web/src/router/index.tsx`
- Modify: `web/src/layouts/dashboard-layout.tsx`
- Add: `web/scripts/test-llm-settings-static.mjs`

- [ ] **Step 1: Add route and menu**

Add route:

```tsx
{
  path: 'settings/llm',
  element: (
    <PermissionGuard permission="tenant.management.view">
      <LlmSettingsAdminPage />
    </PermissionGuard>
  ),
}
```

Add menu item under super admin `settings`:

```ts
{
  key: 'settings-llm',
  label: 'LLM设置',
  icon: 'RobotOutlined',
  path: '/settings/llm',
}
```

- [ ] **Step 2: Build page tabs**

Use Antd `Tabs`:
- `平台厂商与模型`
- `公司授权`
- `测试设置`

Use compact operational UI, not marketing layout.

- [ ] **Step 3: Build provider/model tab**

Provider table columns:
- logo/name
- provider type
- API base URL
- API key masked/configured
- active state
- actions: edit, disable, delete if unused

Model nested table columns:
- display name
- real model name
- active state
- test button
- actions: edit display/active, delete if unused

Key edit behavior:
- New provider requires API key.
- Edit provider empty key means unchanged.
- Response never fills raw key back into the input.

- [ ] **Step 4: Build company authorization tab**

Company-first UI:
- select/search company.
- show provider grouped model tree.
- switch model grant active/inactive.
- choose default model from effective granted models.
- save with one `PUT /settings/llm/tenants/<id>/authorization/`.

- [ ] **Step 5: Build test settings tab**

Fields:
- multiline required `testPrompt`
- numeric `testCooldownSeconds`
- numeric `testTimeoutSeconds`
- numeric `testMaxTokens`

Validate with the same ranges as backend.

- [ ] **Step 6: Add static check**

`web/scripts/test-llm-settings-static.mjs` should assert:
- router has `settings/llm`.
- dashboard menu has `settings-llm`.
- admin page source does not contain `apiKey` display in table columns except masked/configured names.
- company page source does not contain `apiBaseUrl`.

- [ ] **Step 7: Run frontend check**

Run:

```bash
docker compose exec web npm run build
node web/scripts/test-llm-settings-static.mjs
```

Expected: PASS after page implementation.

- [ ] **Step 8: Commit admin page**

Run:

```bash
git add web/src/views/settings-llm/index.tsx web/src/router/index.tsx web/src/layouts/dashboard-layout.tsx web/scripts/test-llm-settings-static.mjs
git commit -m "feat: 增加超管LLM设置页面"
```

## Task 9: Build Company LLM Settings Page

**Files:**
- Create/modify: `web/src/views/llm-settings/index.tsx`
- Modify: `web/src/views/llm-management.ts`
- Modify: `web/src/router/index.tsx`
- Modify: `web/src/layouts/dashboard-layout.tsx`

- [ ] **Step 1: Replace company page behavior**

Company page must:
- load `fetchCompanyLLMOptions`.
- group models by provider.
- show current default.
- show global test prompt.
- allow model test on every visible model.
- allow set default only if `hasPermission('ai_models.llm.update')`.
- never show create/edit/delete provider controls.
- never show API key or API base URL.

- [ ] **Step 2: Rename menu label**

Change company AI model module child label from `LLM管理` to `LLM设置`.

- [ ] **Step 3: Keep export compatibility**

Make `web/src/views/llm-management.ts` export the new company settings page:

```ts
export { LlmSettingsPage as LlmManagementPage } from './llm-settings';
```

- [ ] **Step 4: Run frontend build**

Run:

```bash
docker compose exec web npm run build
node web/scripts/test-llm-settings-static.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit company page**

Run:

```bash
git add web/src/views/llm-settings/index.tsx web/src/views/llm-management.ts web/src/router/index.tsx web/src/layouts/dashboard-layout.tsx web/scripts/test-llm-settings-static.mjs
git commit -m "feat: 改造公司LLM设置页面"
```

## Task 10: Update Chat Room and Application Frontend

**Files:**
- Modify: `web/src/views/chat-room/index.tsx`
- Modify: `web/src/views/application-management/index.tsx`
- Modify: `web/src/api/modules/chat.ts`
- Modify: `web/src/api/modules/applications.ts`

- [ ] **Step 1: Replace provider/model option loading**

Use `fetchCompanyLLMOptions()` to build grouped `Select` options:

```ts
const modelOptions = options.providers.map((provider) => ({
  label: provider.name,
  options: provider.models.map((model) => ({
    label: model.displayName || model.name,
    value: model.id,
  })),
}));
```

- [ ] **Step 2: Replace selected value shape**

Use `llmModelId: number | null` instead of combined `providerId::modelName` strings.

- [ ] **Step 3: Update create/update calls**

Chat:

```ts
await updateConversationConfig(activeId, {
  llmModelId: selectedModelId,
  systemPrompt,
  temperature,
  maxTokens,
});
```

Application:

```ts
llmModelId: values.llmModelId ?? null
```

- [ ] **Step 4: Update empty states**

If no models are available:
- Chat select placeholder: `暂无可用模型，请联系管理员配置 LLM 设置`
- Application form placeholder: `暂无可用模型`

- [ ] **Step 5: Run build**

Run:

```bash
docker compose exec web npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit consumers**

Run:

```bash
git add web/src/views/chat-room/index.tsx web/src/views/application-management/index.tsx web/src/api/modules/chat.ts web/src/api/modules/applications.ts
git commit -m "feat: 聊天和应用使用授权LLM模型"
```

## Task 11: Full Verification

**Files:**
- No new files unless verification reveals defects.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_platform_settings_api apps.ai_models.tests.test_llm_company_settings_api apps.ai_models.tests.test_llm_model_usage apps.ai_models.tests.test_chat_api apps.ai_models.tests.test_agent_application_api apps.tenants.tests.test_llm_isolation apps.tenants.tests.test_isolation_contract
```

Expected: PASS.

- [ ] **Step 2: Run broader tenant and ai_models tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models apps.tenants
```

Expected: PASS.

- [ ] **Step 3: Run frontend build and static checks**

Run:

```bash
docker compose exec web npm run build
node web/scripts/test-llm-settings-static.mjs
```

Expected: PASS.

- [ ] **Step 4: Manual smoke through Docker app**

Run:

```bash
docker compose up -d
```

Open:

```text
http://localhost:5175/settings/llm
http://localhost:5175/ai-models/llm
```

Verify:
- super admin can create provider with key and does not see raw key after save.
- super admin can create model and test it.
- super admin can authorize a model to a company and set default.
- company side sees grouped provider/models, no API URL/key.
- company can test each model and set default with update permission.
- chat and application selectors show authorized models only.
- disabled model disappears and existing bound usage fails closed.

- [ ] **Step 5: Commit verification fixes**

If any fixes were needed:

```bash
git add backend web
git commit -m "fix: 修复LLM设置验证问题"
```

## Task 12: Finish Branch

**Files:**
- No code files.

- [ ] **Step 1: Review final diff**

Run:

```bash
git status --short
git log --oneline --decorate -10
```

Expected: only intended files changed and all work committed.

- [ ] **Step 2: Merge back to main**

Run:

```bash
git switch main
git merge --no-ff dev/llm-settings -m "merge: 合并LLM设置改造"
git branch -d dev/llm-settings
```

Expected: `main` contains the new commits and dev branch is deleted.

## Self-Review

- Spec coverage:
  - Platform shared key: Task 2, Task 4, Task 8.
  - Company authorization and switches: Task 2, Task 4, Task 5, Task 8.
  - Company page cannot create models: Task 5, Task 9.
  - Company default model: Task 2, Task 5, Task 6, Task 9.
  - Global test prompt and configurable test limits: Task 2, Task 4, Task 5, Task 8.
  - Fail-closed model usage: Task 6.
  - Chat/application model selection: Task 6, Task 10.
  - API key masking/no company secrets: Task 4, Task 5, Task 8, Task 9.
  - Audit descriptions and sensitive logging boundary: Task 4.
- Placeholder scan:
  - No unresolved placeholder wording or open-ended implementation steps remain.
- Type consistency:
  - Backend canonical field is `llm_model`.
  - API canonical field is `llmModelId`.
  - Company option model type is `LLMModelOption`.
