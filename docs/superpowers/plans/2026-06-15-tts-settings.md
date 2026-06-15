# TTS Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build platform-level Aliyun TTS settings, provider voice catalog, company default TTS voice selection, browser playback tests, and device runtime PCM synthesis.

**Architecture:** Add platform-owned TTS provider configuration and provider voice catalog models under `apps.ai_models`. Company users store only a default provider voice; management tests return browser-playable WAV while device runtime returns raw PCM with audio metadata headers. The first UI exposes a single Aliyun TTS card, but the backend shape keeps provider voices attached to a provider for future TTS integrations.

**Tech Stack:** Django 5.2, DRF, websockets, React 18, Vite, Antd 5, Docker Compose only.

---

## File Structure

- Modify `backend/apps/ai_models/models.py`: add `TTSProvider`, `TTSVoice`, `TenantTTSSettings`.
- Create `backend/apps/ai_models/services/tts.py`: effective config loading, voice catalog serialization, Aliyun realtime synthesis over `websockets`, PCM-to-WAV wrapping, text chunking.
- Modify `backend/apps/ai_models/serializers.py`: add TTS platform/company serializers.
- Modify `backend/apps/ai_models/views.py`: add platform settings, company options/default voice/test, and device runtime endpoints.
- Modify `backend/apps/ai_models/urls.py`: register `/settings/tts/`, `/settings/tts/test/`, `/ai-models/tts/options/`, `/ai-models/tts/default-voice/`, `/ai-models/tts/test/`, `/ai-models/tts/runtime/`.
- Modify `backend/apps/accounts/permissions.py`: add `CanViewTTS` and `CanUpdateTTS`.
- Create `backend/apps/ai_models/migrations/0015_tts_settings.py`: create tables, seed Aliyun provider and voices from `wiki/voices_qwen3.json`, seed `ai_models.tts.update`.
- Modify `backend/config/settings/base.py`: add TTS env fallback defaults.
- Create `backend/apps/ai_models/tests/test_tts_api.py`: platform settings, company defaults, audio response, device PCM runtime.
- Create `web/src/api/modules/tts.ts`: platform/company TTS API helpers with blob responses.
- Create `web/src/views/tts-settings/index.tsx` and `web/src/views/tts-settings.ts`: super admin settings page.
- Modify `web/src/views/tts-management/index.tsx`: replace placeholder with company default voice/test page.
- Modify `web/src/router/index.tsx`: add `/settings/tts`.
- Modify `web/src/layouts/dashboard-layout.tsx`: add `设置 > TTS设置`.

## Task 1: Backend TTS API Contract

**Files:**
- Test: `backend/apps/ai_models/tests/test_tts_api.py`
- Modify: `backend/apps/accounts/permissions.py`
- Modify: `backend/apps/ai_models/models.py`
- Modify: `backend/apps/ai_models/services/tts.py`
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/views.py`
- Modify: `backend/apps/ai_models/urls.py`
- Modify: `backend/config/settings/base.py`

- [x] **Step 1: Write failing API tests**

Create tests that assert:

```python
class TTSApiTests(TenantTestMixin, APITestCase):
    def test_superuser_can_read_and_update_tts_settings_without_raw_key(self):
        ...

    def test_company_user_can_select_default_voice_without_provider_secrets(self):
        ...

    def test_company_test_returns_wav_wrapped_pcm(self):
        ...

    def test_device_runtime_uses_device_code_and_returns_raw_pcm(self):
        ...
```

- [x] **Step 2: Run RED tests in Docker**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api
```

Expected: fail because TTS models/endpoints do not exist.

- [x] **Step 3: Implement minimal backend models, serializers, services, permissions, and URLs**

Add the three TTS models, permission classes, serializers, service functions, and views needed for those tests:

```python
class TTSProvider(models.Model):
    code = models.CharField(max_length=32, unique=True, default='aliyun')
    name = models.CharField(max_length=128, default='阿里云 TTS')
    api_key = models.CharField(max_length=512, blank=True, default='')
    base_url = models.CharField(max_length=512, blank=True, default='')
    model = models.CharField(max_length=128, blank=True, default='')
    default_voice = models.ForeignKey('TTSVoice', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    sample_rate = models.PositiveIntegerField(default=24000)
    default_test_text = models.TextField(default='对吧~我就特别喜欢这种超市，尤其是过年的时候去逛超市就会觉得超级超级开心！想买好多好多的东西呢！')
    is_active = models.BooleanField(default=True)
```

```python
class TTSVoice(models.Model):
    provider = models.ForeignKey(TTSProvider, on_delete=models.CASCADE, related_name='voices')
    display_name = models.CharField(max_length=128)
    voice_code = models.CharField(max_length=128)
    gender = models.CharField(max_length=16, blank=True, default='')
    avatar_path = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
```

```python
class TenantTTSSettings(models.Model):
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='tts_settings')
    default_voice = models.ForeignKey(TTSVoice, null=True, blank=True, on_delete=models.SET_NULL, related_name='tenant_default_settings')
```

- [x] **Step 4: Run GREEN tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api
```

Expected: all tests in `test_tts_api.py` pass.

## Task 2: Data Migration And Voice Catalog Seed

**Files:**
- Create: `backend/apps/ai_models/migrations/0015_tts_settings.py`
- Test: `backend/apps/ai_models/tests/test_tts_api.py`

- [x] **Step 1: Add failing seed assertions**

Assert the migration/seed creates:

```python
provider = TTSProvider.objects.get(code='aliyun')
self.assertEqual(provider.default_voice.voice_code, 'Cherry')
self.assertTrue(TTSVoice.objects.filter(provider=provider, voice_code='Cherry', avatar_path__contains='voice_female_one.png').exists())
self.assertTrue(PermissionPoint.objects.filter(code='ai_models.tts.update').exists())
```

- [x] **Step 2: Run RED tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api
```

Expected: fail because seed data is missing.

- [x] **Step 3: Add migration seed**

Read `wiki/voices_qwen3.json` during migration from repository root if present, seed all voices with deterministic `sort_order`, and fall back to a hard-coded Cherry row if the wiki file is unavailable.

- [x] **Step 4: Run migration test**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api
```

Expected: pass.

## Task 3: Frontend API And Pages

**Files:**
- Create: `web/src/api/modules/tts.ts`
- Create: `web/src/views/tts-settings/index.tsx`
- Create: `web/src/views/tts-settings.ts`
- Modify: `web/src/views/tts-management/index.tsx`
- Modify: `web/src/router/index.tsx`
- Modify: `web/src/layouts/dashboard-layout.tsx`

- [x] **Step 1: Add static/type checks by wiring imports first**

Add `tts.ts` API methods:

```ts
export const fetchTtsSettings = async () => httpClient.get<TtsSettings>('/settings/tts/');
export const updateTtsSettings = async (payload: TtsSettingsPayload) => httpClient.patch<TtsSettings>('/settings/tts/', payload);
export const testPlatformTts = async (payload: TtsTestPayload) => httpClient.post<Blob>('/settings/tts/test/', payload, { responseType: 'blob' });
export const fetchCompanyTtsOptions = async () => httpClient.get<CompanyTtsOptions>('/ai-models/tts/options/');
export const updateCompanyDefaultTtsVoice = async (voiceId: number) => httpClient.patch<CompanyTtsOptions>('/ai-models/tts/default-voice/', { voiceId });
export const testCompanyTts = async (payload: TtsTestPayload) => httpClient.post<Blob>('/ai-models/tts/test/', payload, { responseType: 'blob' });
```

- [x] **Step 2: Run RED type check**

Run:

```bash
docker compose exec web npm run build
```

Expected: fail until views/routes are fully wired.

- [x] **Step 3: Implement super admin TTS settings page**

Build `TtsSettingsPage` with:
- Aliyun TTS config card: API key, WebSocket URL, model, sample rate, default test text, active switch.
- Voice list: built-in avatar, name, voice code, gender, active/visible toggles, default marker.
- Test area: optional text input and playback of WAV blob.

- [x] **Step 4: Implement company TTS management page**

Replace placeholder with:
- Current default voice.
- Provider voice grid/list from enabled visible voices only.
- Save default voice.
- Optional test text and playback of WAV blob.
- No API key, base URL, model, or provider secret fields.

- [x] **Step 5: Run GREEN type check**

Run:

```bash
docker compose exec web npm run build
```

Expected: build passes.

## Task 4: Docker Verification And Commit

**Files:**
- All modified files

- [x] **Step 1: Run backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api apps.ai_models.tests.test_asr_api apps.ai_models.tests.test_llm_company_settings_api apps.ai_models.tests.test_llm_platform_settings_api
```

Expected: pass.

- [x] **Step 2: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: pass.

- [x] **Step 3: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only TTS feature files, `CONTEXT.md`, and the user-provided wiki files as untracked inputs.

- [ ] **Step 4: Commit in Chinese**

Run:

```bash
git add CONTEXT.md docs/superpowers/plans/2026-06-15-tts-settings.md backend web
git commit -m "实现阿里云TTS平台配置与公司音色选择"
```

Expected: local commit created; no remote push.

## Self-Review

- Spec coverage: platform `设置 > TTS设置`, company `AI大模型 > TTS管理`, JSON voice import, browser testing, device PCM runtime, env fallback, no company secrets, and company default voice are all covered.
- Placeholder scan: no implementation placeholders remain in this plan.
- Type consistency: backend uses `voiceId`, `voiceCode`, `sampleRate`, `defaultTestText`; frontend mirrors those names.
