# TTS Tenant Card Authorization

> How company-side TTS is gated, how vendor differences are isolated, and what must
> stay frozen for Android.

---

## Scenario: Company TTS is card-authorization gated

### 1. Scope / Trigger

- Trigger: any change to company TTS visibility, device voice binding, HTTP runtime
  TTS, unified realtime TTS, or the addition of a new TTS vendor.
- Code-spec depth is mandatory here: the change spans a DB schema addition, a
  cross-layer response contract, a WebSocket routing contract, and a frozen
  Android runtime contract.

A TTS **card** is a `TTSProvider` row. Authorization granularity is the card, never
the individual voice. A company sees a voice when **all** of the following hold:

```
active TenantTTSProviderGrant(tenant, provider)
  AND provider.is_active
  AND voice.is_active AND voice.is_visible
```

Effective voices are always *derived* from that predicate — never stored, never
cached in a column. A newly added voice on an already-granted card is therefore
immediately usable with no extra write.

### 2. Signatures

Model — `backend/apps/ai_models/models.py`:

```python
class TenantTTSProviderGrant(models.Model):
    tenant = FK('tenants.Tenant', related_name='tts_provider_grants')
    provider = FK(TTSProvider, related_name='tenant_grants')     # the card
    is_active = BooleanField(default=True)
    public_config = JSONField(default=dict)                       # per-card controls
    objects = TenantManager()
    # UniqueConstraint(fields=['tenant', 'provider'], name='uniq_tenant_tts_provider_grant')
```

Authorization service — `backend/apps/ai_models/services/tts_authorization.py`.
This module is the **only** sanctioned way to answer "may this company use this
voice?":

```python
get_effective_tts_voices_for_tenant(tenant, *, provider_code=None, model_code=None)
get_effective_tts_voice_for_tenant(tenant, *, provider_code=None, model_code=None)
ensure_tts_voice_authorized_for_tenant(tenant, raw_voice_id, *, field='voiceId')  # raises 400
resolve_tenant_tts_voice(tenant, raw_voice_id=None, *, allow_fallback=True)
resolve_device_tts_voice(device, raw_voice_id=None, *, model_code=None)
get_tenant_tts_card_public_config(tenant, provider)
tts_provider_usage_for_tenant(tenant, provider)   # -> usage dict
tts_provider_grant_is_in_use(tenant, provider)
tts_provider_has_active_company_authorization(provider)
```

Super-admin REST:

```
GET  /api/v1/settings/tts/tenants/{tenantId}/card-authorizations/    # IsSuperUser
PUT  /api/v1/settings/tts/tenants/{tenantId}/card-authorizations/    # IsSuperUser
```

### 3. Contracts

`PUT` request:

```json
{
  "cardGrants": [
    {"providerId": 10, "isActive": true, "publicConfig": {"speech_rate": 1.2}}
  ],
  "defaultVoiceId": 101
}
```

`GET`/`PUT` response: `{tenant, providers[], defaultVoiceId}`. Each provider entry
carries `grantIsActive`, `publicConfig`, `publicConfigSchema`, `supportedChannels`,
`usage`, `canDisableGrant`, and `voices[]` (each with `effectiveAuthorized`,
`isDefault`, `usage`).

Company options (`GET /api/v1/ai-models/tts/options/`) is provider-neutral and
additive — the legacy fields stay for the migration window:

| Field | Meaning |
|-------|---------|
| `voices[]` | flat union of every authorized card's voices (legacy consumers) |
| `provider` | summary of the **default voice's** card; empty/inactive when no grant |
| `providers[]` | per-card groups, each with `publicConfigSchema` and `voices[]` |
| `ttsSessionConfig` | default card's normalized public controls (not an upstream payload) |

Every voice carries its card identity so the UI can pick the right schema:
`providerId`, `providerCode`, `providerName`, `configSchemaKey`,
`supportedChannels`, `capabilities`.

**Never** present in any company-, device-, or realtime-facing response: `api_key`,
`base_url` / `websocket_url` / `customization_url`, or vendor-private request
parameters.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| `voiceId` unauthorized / unknown / hidden / disabled / another tenant's | 400 `所选音色未授权或已停用` — one message for all, so ids cannot be probed |
| `tenantId` missing or inactive | 400 `公司不存在或已停用` |
| `defaultVoiceId` not under a card enabled in the same request | 400 |
| `defaultVoiceId` disabled / hidden / card disabled | 400 |
| `publicConfig` contains a field outside that card's schema | 400 naming the field |
| Disabling a grant still referenced by company default / device / device application | 400 with usage summary; grant row is left untouched |
| Tenant holds no grant at all | 400 `当前公司暂无可用 TTS 音色，请联系超管分配` (options returns an empty state instead) |
| Adapter missing, unconfigured, or channel unsupported | explicit error / `tts.error`; **never** a cross-card fallback |

### 5. Good/Base/Bad Cases

- **Good**: super admin grants CosyVoice to company A; A's options immediately list
  its voices, binds one to a device, and realtime streams through the CosyVoice
  adapter.
- **Base**: upgrade of an existing deployment — migration `0045` seeds Aliyun/Qwen
  grants for every active tenant, so company behaviour is unchanged and no
  CosyVoice access is granted implicitly.
- **Bad**: resolving a card from a client-supplied `providerCode`, or falling back
  to the platform default voice when a company's binding becomes unauthorized.
  Both let a company reach a card it was never granted.

### 6. Tests Required

| Module | Assertion points |
|--------|------------------|
| `apps.ai_models.tests.test_tts_authorization` | derived-visibility predicate, inactive grant, disabled card/voice, cross-tenant rejection, fallback stays inside authorization, per-card config isolation, usage counting |
| `apps.ai_models.tests.test_tts_adapters` | registry rejects unknown card, routing comes from `voice.provider`, per-card schema whitelist, CosyVoice task protocol + chunk forwarding, provider summary hides credentials |
| `apps.ai_models.tests.test_tts_card_authorization_api` | superuser-only, per-card `publicConfig` isolation, blocked disable with usage counts, default-voice validation, runtime-config publish |
| `apps.ai_models.tests.test_company_tts_options_api` | empty state, only-authorized voices, grouped + flat shape, no credential leakage, revoked grant disappears |
| `apps.devices.tests.test_device_tts_authorization` | binding rejection/acceptance, binding beats company default, revoked binding falls back, frozen Android payload keys, HTTP runtime headers, full-config WS push |

### 7. Wrong vs Correct

#### Wrong

```python
# Trusts the client's providerCode as the router and queries voices globally.
provider = resolve_tts_provider(payload.get('providerCode'))
voice = TTSVoice.objects.filter(id=payload['voiceId'], provider=provider).first()
```

#### Correct

```python
# The authorized voice is the router; providerCode may only confirm it.
voice = ensure_tts_voice_authorized_for_tenant(tenant, payload['voiceId'])
adapter = get_adapter_for_voice(voice)
adapter.ensure_channel(voice.provider, CHANNEL_REALTIME)
config = adapter.effective_config(voice.provider)
```

---

## Scenario: Provider adapter seam

### 1. Scope / Trigger

- Trigger: adding a TTS vendor, or touching how an upstream request payload is built.
- Vendor differences (credentials, protocol, parameter names) live **only** inside an
  adapter. Callers see one generic control vocabulary.

### 2. Signatures

`backend/apps/ai_models/services/tts_adapters.py`:

```python
CHANNEL_HTTP_TEST = 'httpTest'
CHANNEL_HTTP_RUNTIME = 'httpRuntime'
CHANNEL_REALTIME = 'realtime'

class BaseTTSAdapter:
    provider_code: str
    schema_key: str
    supports_company_http_test / _http_runtime / _realtime: bool
    config_fields: tuple[ConfigField, ...]

    supported_channels(provider) -> list[str]
    company_runtime_capabilities(provider) -> dict[str, bool]
    public_provider_summary(provider) -> dict      # safe; no credentials
    public_config_schema(provider) -> dict         # {schemaKey, fields[]}
    normalize_public_controls(raw) -> dict         # whitelist; raises on unknown key
    effective_config(provider) -> EffectiveTTSConfig
    ensure_channel(provider, channel) -> None      # raises TTSAdapterError
    ensure_voice_supported(voice, controls) -> None
    synthesize_pcm(*, text, voice, config, controls) -> bytes
    async stream_realtime_text(*, text, voice, config, send, controls, exclude_patterns)
    async stream_realtime_segments(*, segments, voice, config, send, controls, exclude_patterns)

get_tts_provider_adapter(provider_code) -> BaseTTSAdapter   # raises on unknown
get_adapter_for_voice(voice) -> BaseTTSAdapter              # the routing entry point
```

### 3. Contracts

- Dispatch is **always** `get_adapter_for_voice(resolved_voice)`. A card code taken
  from request data must never select the adapter.
- `normalize_public_controls` rejects any key not in that card's `config_fields`.
  This is what keeps Qwen's `model_code` / `instructions` out of a CosyVoice payload
  and vice versa.
- Per-card controls live in `TenantTTSProviderGrant.public_config`. Saving one card's
  config never touches another's.
- A card whose adapter is not registered is excluded from the super-admin allocation
  list, so it cannot be granted and then fail at runtime.
- The allocation list is the **intersection** of `grantable_tts_providers()` (rows in
  `TTSProvider`) and the adapter registry, so a registered adapter with no seeded row
  is just as invisible as an unregistered one. Every shipped card therefore needs an
  idempotent data migration creating its `TTSProvider` row — `0015_tts_settings` for
  `aliyun`, `0047_seed_cosyvoice_provider` for `cosyvoice`. A settings model that is a
  OneToOne on `TTSProvider` (`CosyVoiceSettings`, added by `0043`) does not create the
  row it points at.
- A seeding migration uses `get_or_create`, never `update_or_create`: production card
  rows are configured by hand, so the migration fills a missing card and never
  overwrites a configured `api_key` / `base_url` / `model` / `sample_rate` /
  `tts_session_config` / `default_voice`. Its reverse is `RunPython.noop` — a data
  migration cannot tell the row it created from a pre-existing one, and deleting a card
  cascades into `TenantTTSProviderGrant`.
- `model_code` is Aliyun/Qwen-specific. Voice filtering by it must be scoped to the
  `aliyun` card — other cards do not share Qwen's voice-code vocabulary.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Unknown / empty `provider_code` | `TTSAdapterError` — no fallback adapter |
| Voice with no `provider` | `TTSAdapterError` |
| Control key outside the card's schema | `TTSAdapterError` naming the key(s) |
| Channel unsupported by the card | `TTSAdapterError` from `ensure_channel` |
| Card configured but credentials missing | error before any outbound I/O |

### 5. Good/Base/Bad Cases

- **Good**: a new card ships as one adapter class, its super-admin settings page, and a
  data migration seeding its `TTSProvider` row; the grant table, company options,
  device binding and runtime resolution are untouched.
- **Base**: Qwen keeps its historical `_normalize_session_config` bounds by delegating
  to it from the adapter, so existing behaviour is bit-for-bit unchanged.
- **Bad**: widening a shared `session_config` dict with a new vendor's fields, or
  filtering every card's voices by Qwen's `model_code` (silently empties other cards).
  Equally bad: registering an adapter but leaving its card as hand-entered production
  data — it works on the one database somebody typed it into and is permanently
  unallocatable on every fresh deployment, CI database, and new customer.

### 6. Tests Required

`apps.ai_models.tests.test_tts_adapters` — registry rejection, routing from
`voice.provider`, per-card schema keys and field sets, cross-card field rejection,
bounded control coercion, and `json.dumps(public_provider_summary(...))` containing
neither api key nor upstream URL.

### 7. Wrong vs Correct

#### Wrong

```python
# One shared config object; vendor fields leak across cards.
session_config = {**tenant_settings.tts_session_config, **request.data['ttsSessionConfig']}
pcm = synthesize_tts_pcm(text=text, voice=voice, session_config=session_config)
```

#### Correct

```python
adapter = get_adapter_for_voice(voice)
controls = adapter.normalize_public_controls(
    {**get_tenant_tts_card_public_config(tenant, voice.provider), **overrides}
)
pcm = adapter.synthesize_pcm(text=text, voice=voice, config=adapter.effective_config(voice.provider), controls=controls)
```

---

## Scenario: Unified realtime TTS voice routing

### 1. Scope / Trigger

- Trigger: any change to `tts.session.start`, `_run_tts_session_body`, or
  `_run_agent_tts_stream`.
- Both the audio stream and the runtime-config subscription share the single
  `/ws/realtime/` endpoint. Adding a business WebSocket URL is forbidden.

### 2. Signatures

```python
# backend/apps/ai_models/realtime_tts.py
@dataclass(frozen=True)
class RealtimeVoiceResolution:
    voice: TTSVoice | None = None
    error_key: str | None = None

resolve_realtime_tts_voice(connection, raw_voice_id=None, *, provider_code=None, model_code=None)
    -> RealtimeVoiceResolution
```

Downstream event contract is unchanged: `tts.ready` → `tts.segment_start` → binary
audio frames → `tts.segment_end` → `tts.done`, with `tts.cancelled` / `tts.error`.

### 3. Contracts

- Routing key precedence: explicit `voiceId` → device binding → company default →
  first authorized voice.
- `payload.providerCode` is **optional and advisory**. It may only be compared with
  `voice.provider.code`; it must never select the card. Clients that omit it keep
  working unchanged.
- Upstream protocol per card: Qwen uses `session.update` / `input_text_buffer.append`
  / `input_text_buffer.commit` / `session.finish`; CosyVoice uses `run-task` /
  `continue-task` / `finish-task`.
- CosyVoice segment streaming opens **one upstream task per downstream segment** over
  a shared connection. The task protocol delimits audio per task, not per
  `continue-task`, so this is what keeps `tts.segment_start` / `tts.segment_end`
  aligned with the audio a client actually hears.
- Upstream audio frames are forwarded as they arrive. Accumulating a complete buffer
  before sending defeats the channel and is a defect, not an optimization.

### 4. Validation & Error Matrix

| Condition | Catalogue key | Client result |
| --- | --- | --- |
| Connection cannot be resolved | `TTS_UNAUTHORIZED` | `tts.error` `1023` |
| Adapter missing / unconfigured / channel unsupported | `TTS_NOT_READY` | `tts.error` `1024` |
| No authorized voice resolvable | `TTS_VOICE_NOT_AVAILABLE` | `tts.error` `1025` |
| `providerCode` contradicts the resolved voice's card | `TTS_VOICE_NOT_AVAILABLE` | `tts.error` `1025` + server-side warning log |

> **Warning**: `providerCode='cosyvoice'` used to be rejected outright with `1024`.
> That guard is gone — CosyVoice is now routable and authorization-gated, so an
> ungranted tenant gets `1025` from voice resolution instead.

### 5. Good/Base/Bad Cases

- **Good**: an old client sends only `voiceId`; the backend resolves the card from the
  voice and streams through the matching adapter.
- **Base**: a device sends no `voiceId`; its binding resolves, and if that binding lost
  its grant the company default is used instead.
- **Bad**: honouring a mismatched `providerCode` (card hopping), or returning
  `TTS_NOT_READY` for a card that is merely ungranted (masks the real cause).

### 6. Tests Required

`config.tests.test_realtime_websocket.RealtimeTTSVoiceRoutingTests` — needs DB access
for grants, so it is a `TestCase`, not part of the `SimpleTestCase` suite above it.
Assert: ungranted tenant → `1025`; contradicting `providerCode` → `1025`; absent
`providerCode` → `tts.ready` + `tts.done` with no `tts.error`.

### 7. Wrong vs Correct

#### Wrong

```python
if provider_code == COSYVOICE_PROVIDER_CODE:
    return None   # blanket refusal; conflates "not allowed" with "not ready"
```

#### Correct

```python
resolution = resolve_realtime_tts_voice(connection, payload.get('voiceId'),
                                        provider_code=payload.get('providerCode'))
if resolution.voice is None:
    await _send_realtime_error(send, 'tts.error', command_id,
                               resolution.error_key or 'TTS_VOICE_NOT_AVAILABLE')
    return
```

---

## Scenario: Frozen Android runtime TTS contract

### 1. Scope / Trigger

- Trigger: any edit to `DeviceRuntimeConfigView`, `_voice_payload`, `TTSRuntimeView`,
  or `device_tts_session_config`.
- Multi-card authorization must not require an Android release. New response fields
  may only ever be optional and additive.

### 2. Signatures

```
GET  /api/v1/device-runtime/config/     header: X-Device-Code
POST /api/v1/ai-models/tts/runtime/     header: X-Device-Code
```

### 3. Contracts

- `resources.voiceTones` stays an array holding **only the voice currently in use** —
  never a candidate list.
- Each voice item keeps exactly: `id`, `name`, `voiceCode`, `audioUrl`, `iconUrl`,
  `speechRate`, `pitchRate`, `volume`.
- HTTP runtime TTS returns an audio body with `Content-Type: audio/pcm` or
  `audio/wav`, plus `X-Audio-Source-Format`, `X-Audio-Sample-Rate`,
  `X-Audio-Channels`, `X-TTS-Voice`.
- Android sends only `X-Device-Code`, `text`, an optional `voiceId`, and generic audio
  flags. It must never be required to send `providerCode` or any vendor-private field.
- Tenant is derived from the device, never from request data.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Device binding lost its card grant | treated as invalid; falls back to company default, then first authorized voice |
| No authorized voice at all | `resources.voiceTones: []` (config) / 400 (runtime TTS) |
| `voiceId` outside the device tenant's authorization | 400 |

### 5. Good/Base/Bad Cases

- **Good**: a CosyVoice voice is bound; Android reads the same field set it always did.
- **Base**: no explicit binding; the device follows the company default and picks up
  changes via the runtime-config push.
- **Bad**: returning the unauthorized bound voice, or adding a required `providerCode`
  to the runtime payload.

### 6. Tests Required

`apps.devices.tests.test_device_tts_authorization` — assert the voice payload key set
**exactly** (`assertEqual(set(voice), {...})`, so an accidental additive-but-required
field is caught), the runtime response headers, and revoked-binding fallback.

### 7. Wrong vs Correct

#### Wrong

```python
voice = getattr(device, 'tts_voice', None)
if voice is None:
    return get_effective_tts_voice_for_tenant(device.tenant)   # may be unauthorized
return voice                                                   # binding never re-checked
```

#### Correct

```python
return tts_auth.resolve_device_tts_voice(device)
```

---

## Scenario: Runtime-config push after an authorization change

### 1. Scope / Trigger

- Trigger: changing a card grant, a card's `public_config`, the company default voice,
  or a provider/voice's active/visible flags.
- These change a device's effective voice **without writing to the `Device` row**, so
  nothing else would notify an online device.

### 2. Signatures

```python
# backend/apps/ai_models/services/tts_runtime_events.py
publish_tenant_tts_config_changed(tenant_id) -> None
publish_tts_provider_authorization_changed(provider) -> None
publish_tts_voice_authorization_changed(voice) -> None
```

### 3. Contracts

- Reuses the existing tenant-level event; no new event type and no new WebSocket URL:

```json
{
  "type": "device.voice_configuration.changed",
  "tenantId": 2,
  "refresh": {"endpoint": "/api/v1/device-runtime/config/", "reason": "voiceConfigurationChanged"}
}
```

- Subscribers of `device.runtime_config.subscribe` receive a **fully rebuilt** config
  via `DeviceRuntimeConfigView._config_payload`, never a voice-only delta. Each device
  therefore keeps its own binding while devices without one follow the new default.
- Publication is queued with `transaction.on_commit`, so a rolled-back save never
  notifies.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| `tenant_id` is `None` | no-op |
| Device-level binding change | keeps using the existing device-level event |
| Grant/config/default change | tenant-level event; devices are not enumerated |

### 5. Good/Base/Bad Cases

- **Good**: super admin saves an authorization; a subscribed device immediately receives
  `device.runtime_config.subscribed` with `action=voiceConfigurationChanged` and a full config.
- **Base**: no subscriber is connected; the next HTTP `config` fetch is already correct.
- **Bad**: relying on the frontend to refresh, or pushing only the changed `voiceId`.

### 6. Tests Required

`apps.devices.tests.test_device_tts_authorization.TTSAuthorizationRuntimeConfigPushTests`
— subscribe over `/ws/realtime/`, save the authorization, assert
`action == 'voiceConfigurationChanged'` and that the payload contains `device`,
`application`, `agentApplication`, `wakeWords`, `scrollingTexts`, plus the expected voice.

> **Warning**: `transaction.on_commit` callbacks do not fire inside a `TestCase`'s
> wrapping atomic block. Wrap the request in `self.captureOnCommitCallbacks(execute=True)`
> or the assertion will time out waiting for an event that was never dispatched. In a
> WebSocket test the request runs through `sync_to_async`, so the capture must live
> inside the wrapped callable.

