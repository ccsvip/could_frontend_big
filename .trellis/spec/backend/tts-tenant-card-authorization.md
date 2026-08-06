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

A TTS **card** is a `TTSProvider` row. Authorization has two levels: the card, and —
when the card grant is in `selected` mode — the individual voice. A company sees a
voice when **all** of the following hold:

```
active TenantTTSProviderGrant(tenant, provider)
  AND provider.is_active
  AND voice.is_active AND voice.is_visible          # 平台上架, platform-global
  AND (voice.owner_tenant IS NULL OR voice.owner_tenant == tenant)
  AND (grant.grant_mode == 'all'
       OR active TenantTTSVoiceGrant(tenant, voice))
```

`is_visible` is **platform listing (平台上架), not per-company visibility** — it is a
global shelf flag with no tenant in it. Per-company scoping is `grant_mode` +
`TenantTTSVoiceGrant` + `owner_tenant`; reaching for `is_visible` to hide a voice from
one company hides it from every company.

The card conditions and `grant_mode` must stay inside **one** `.filter()` call so they
match the same joined grant row. Split across two calls, Django matches them
independently: "some grant row on this card is active for us" AND "some grant row on
this card is `all`" — and the second row may belong to another company, silently
widening our `selected` card back to the whole card.

Effective voices are always *derived* from that predicate — never stored, never
cached in a column. A newly added voice on an `all`-mode granted card is therefore
immediately usable with no extra write; on a `selected`-mode card it requires a tick,
which is the point of that mode.

### 2. Signatures

Model — `backend/apps/ai_models/models.py`:

```python
class TenantTTSProviderGrant(models.Model):
    tenant = FK('tenants.Tenant', related_name='tts_provider_grants')
    provider = FK(TTSProvider, related_name='tenant_grants')     # the card
    is_active = BooleanField(default=True)
    grant_mode = CharField(choices=[('all', '全部音色'), ('selected', '指定音色')],
                           default='all')                        # GRANT_MODE_ALL / _SELECTED
    public_config = JSONField(default=dict)                       # per-card controls
    objects = TenantManager()
    # UniqueConstraint(fields=['tenant', 'provider'], name='uniq_tenant_tts_provider_grant')

class TenantTTSVoiceGrant(models.Model):
    tenant = FK('tenants.Tenant', related_name='tts_voice_grants')
    voice = FK(TTSVoice, related_name='tenant_grants')
    is_active = BooleanField(default=True)
    # UniqueConstraint(fields=['tenant', 'voice'], name='uniq_tenant_tts_voice_grant')

class TTSVoice(models.Model):
    owner_tenant = FK('tenants.Tenant', null=True, blank=True,
                      related_name='owned_tts_voices')            # null = platform-public
    is_visible = BooleanField(default=True, verbose_name='平台上架')
```

Migrations `0049` (grant mode + voice grants), `0050` (`owner_tenant`), `0051`
(`is_visible` label) are deliberately split so each piece reverts on its own. All three
are additive with no backfill: every existing voice becomes platform-public and every
existing card grant becomes `all`, so an upgraded deployment behaves identically.

Authorization service — `backend/apps/ai_models/services/tts_authorization.py`.
This module is the **only** sanctioned way to answer "may this company use this
voice?":

```python
get_effective_tts_voices_for_tenant(tenant, *, provider_code=None, model_code=None)
get_effective_tts_voice_for_tenant(tenant, *, provider_code=None, model_code=None)
is_tts_voice_effective_for_tenant(tenant, voice, *, model_code=None)
ensure_tts_voice_authorized_for_tenant(tenant, raw_voice_id, *, field='voiceId')  # raises 400
resolve_tenant_tts_voice(tenant, raw_voice_id=None, *, allow_fallback=True)
resolve_device_tts_voice(device, raw_voice_id=None, *, model_code=None)
get_tenant_tts_provider_grant(tenant, provider)
tts_voice_grant_ids_for_tenant(tenant, provider)  # -> set[int], active ticks on one card
get_tenant_tts_card_public_config(tenant, provider)
tts_provider_has_active_company_authorization(provider)
tts_voice_has_active_company_authorization(voice)
grantable_tts_providers()
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
    {"providerId": 10, "isActive": true, "grantMode": "all",
     "publicConfig": {"speech_rate": 1.2}},
    {"providerId": 11, "isActive": true, "grantMode": "selected", "voiceIds": [101, 104]}
  ],
  "defaultVoiceId": 101
}
```

`grantMode` is optional and defaults to `all`, so a pre-voice-grant client's payload
keeps its old meaning. `voiceIds` is **required** when `grantMode='selected'` and
ignored otherwise — `all` must not clear the existing ticks, because the super-admin
can no longer see them and switching back to `selected` would come up empty.

Validation is made against the voice set **the save would produce**, derived from the
payload — not against the database. Reading the DB answers for the state *before* the
save, which is exactly how one PUT could both un-tick a voice and make it the default.
Cards absent from `cardGrants` keep whatever they have today, because `put` only writes
the cards it was given.

`GET`/`PUT` response: `{tenant, providers[], defaultVoiceId}`. Each provider entry
carries `grantIsActive`, `grantMode`, `authorizedVoiceCount`, `publicConfig`,
`publicConfigSchema`, `supportedChannels`, and `voices[]` (each with
`voiceGrantIsActive`, `effectiveAuthorized`, `ownerTenant`, `isDefault`).

Super-admin revocation is unconditional. The page must allow a card or selected-mode
voice to be revoked even when the company default, a device, or a device application
still references it. Those references stay intact; subsequent runtime resolution uses
the existing authorization predicate and fallback rules.

Voices owned by **another** company are absent from the response entirely — not
rendered as un-ticked rows — so one company's page never leaks another's cloned voices.

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
| `voiceId` unauthorized / unknown / hidden / disabled / un-ticked / another tenant's private | 400 `所选音色未授权或已停用` — one message for all, so ids cannot be probed |
| `tenantId` missing or inactive | 400 `公司不存在或已停用` |
| `grantMode` outside `all` / `selected` | 400 `grantMode 必须是 all 或 selected` |
| `grantMode='selected'` without `voiceIds` | 400 `grantMode=selected 时必须提供 voiceIds` |
| `voiceIds` not an array / element not a positive int | 400 |
| `voiceIds` element unknown **or** another company's private voice | 400 `{card} 下不存在该音色：{id}` — same message for both, so a save cannot probe another company's voice ids |
| `defaultVoiceId` not under a card enabled in the same request | 400 |
| `defaultVoiceId` disabled / hidden / card disabled | 400 `默认音色或所属卡片未启用` |
| `defaultVoiceId` not in the set this save would produce (un-ticked, unlisted, or another company's) | 400 `默认音色本次保存后不可用（未上架、未勾选或不属于该公司）` |
| `publicConfig` contains a field outside that card's schema | 400 naming the field |
| Super-admin disables a grant or un-ticks a referenced voice | 200; authorization is revoked even when company default / device / device application references remain |
| Tenant holds no grant at all | 400 `当前公司暂无可用 TTS 音色，请联系超管分配` (options returns an empty state instead) |
| Adapter missing, unconfigured, or channel unsupported | explicit error / `tts.error`; **never** a cross-card fallback |

### 5. Good/Base/Bad Cases

- **Good**: super admin grants CosyVoice to company A; A's options immediately list
  its voices, binds one to a device, and realtime streams through the CosyVoice
  adapter. Narrowing the card to `selected` with two ticks immediately narrows A's
  options, device candidate set, preview and realtime to those two.
- **Base**: upgrade of an existing deployment — migration `0045` seeds Aliyun/Qwen
  grants for every active tenant, so company behaviour is unchanged and no
  CosyVoice access is granted implicitly. `0049`–`0051` add voice-level authorization
  with every card defaulting to `all` and every voice platform-public, so the upgrade
  itself changes nothing a company can observe.
- **Bad**: resolving a card from a client-supplied `providerCode`, or falling back
  to the platform default voice when a company's binding becomes unauthorized.
  Both let a company reach a card it was never granted. Equally bad: using
  `is_visible` to hide a voice from one company (it is a platform-global shelf flag —
  it hides the voice from everybody), or validating `defaultVoiceId` against the
  database instead of the payload's derived set.

### 6. Cloned voice ownership

CosyVoice clones (`enroll` / `design`, both `IsSuperUser`) accept an optional
`ownerTenantId`. Omitted or null keeps the clone platform-public, behaving exactly as
before the field existed; a company id makes the voice private to that company on
every card-authorization and runtime path — `owner_tenant` is in the derivation
predicate, so no separate enforcement exists or is needed.

```python
class CosyVoiceOwnerTenantMixin(serializers.Serializer):
    ownerTenantId = serializers.IntegerField(source='owner_tenant', required=False, allow_null=True)
```

`source='owner_tenant'` plus the views' existing `**serializer.validated_data` call
style routes the validated `Tenant` straight into `_create_voice`'s kwarg — the views
need no change. An unknown or inactive company id is 400 `公司不存在或已停用`.

A cloned voice's `sort_order` stays platform-wide (`count()` over the whole card), so a
company-owned clone does not restart the ordering and land on top of the shared voices.

### 7. Tests Required

| Module | Assertion points |
|--------|------------------|
| `apps.ai_models.tests.test_tts_authorization` | derived-visibility predicate, inactive grant, disabled card/voice, `selected` mode narrowing, one-`.filter()` cross-tenant grant-row leak, `owner_tenant` scoping, cross-tenant rejection, fallback stays inside authorization, per-card config isolation |
| `apps.ai_models.tests.test_tts_adapters` | registry rejects unknown card, routing comes from `voice.provider`, per-card schema whitelist, CosyVoice task protocol + chunk forwarding, provider summary hides credentials |
| `apps.ai_models.tests.test_tts_card_authorization_api` | superuser-only, per-card `publicConfig` isolation, unconditional card/voice revocation despite references, default-voice validation against the post-save set, `all`↔`selected` round trip preserving ticks, another company's private voice hidden and unusable, anti-probing message equality, runtime-config publish |
| `apps.ai_models.tests.test_tts_api` (`CosyVoiceApiTests`) | clone without `ownerTenantId` stays platform-public, clone with it is private to that company, unknown/inactive company rejected |
| `apps.ai_models.tests.test_company_tts_options_api` | empty state, only-authorized voices, grouped + flat shape, no credential leakage, revoked grant disappears |
| `apps.devices.tests.test_device_tts_authorization` | binding rejection/acceptance, binding beats company default, revoked binding falls back, frozen Android payload keys, HTTP runtime headers, full-config WS push |

> The anti-probing assertion compares the two error bodies as strings after
> substituting the ids out, so the messages cannot drift apart:
> `str(rejected.data).replace(str(private_id), 'X') == str(unknown.data).replace('999999', 'X')`.

### 8. Wrong vs Correct

#### Wrong

```python
# Trusts the client's providerCode as the router and queries voices globally.
provider = resolve_tts_provider(payload.get('providerCode'))
voice = TTSVoice.objects.filter(id=payload['voiceId'], provider=provider).first()

# Validates the default against the DB — i.e. against the state before this save.
if not voice.is_visible:
    raise ValidationError({'defaultVoiceId': '默认音色未对外展示'})

# Clears the ticks whenever the card is not in `selected` mode.
TenantTTSVoiceGrant.objects.filter(tenant=tenant, voice__provider=provider).update(is_active=False)
```

#### Correct

```python
# The authorized voice is the router; providerCode may only confirm it.
voice = ensure_tts_voice_authorized_for_tenant(tenant, payload['voiceId'])
adapter = get_adapter_for_voice(voice)
adapter.ensure_channel(voice.provider, CHANNEL_REALTIME)
config = adapter.effective_config(voice.provider)

# Validate against what this save would produce.
after_voice_ids = self._voice_ids_after_save(tenant, normalized_grants, before_voice_ids)
if voice.id not in after_voice_ids:
    raise ValidationError({'defaultVoiceId': '默认音色本次保存后不可用（未上架、未勾选或不属于该公司）'})

# Only `selected` rewrites the ticks.
if entry['grantMode'] != TenantTTSProviderGrant.GRANT_MODE_SELECTED:
    return
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

# backend/config/realtime.py
async def _prepare_agent_tts(connection, command_id, device_code, request_id, trace_id, payload)
    -> tuple[_AgentTTSBundle | None, str]
async def _agent_tts_worker(send, connection, command_id, device_code, request_id, trace_id, payload)
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
- `_agent_tts_worker` resolves the authorized voice, card config and session controls,
  then calls `adapter.prepare_realtime_stream(...)` **before** `queue.get()`. This
  makes the six thread-sensitive ORM operations plus the supported card's upstream
  handshake overlap LLM TTFT. It returns an existing TTS error key but must not send
  `agent.error` or cancel the LLM task.
- A CosyVoice prewarmed handle has already sent one `run-task` and received
  `task-started`. The whole answer appends chunks with `continue-task`, sends one
  `finish-task`, and has one concurrent reader that forwards PCM as it arrives.
- Downstream event types and ordering stay `tts.ready` → `tts.segment_start` → PCM →
  `tts.segment_end` → `tts.done`. CosyVoice task framing does not identify which
  `continue-task` produced an audio frame, so segment markers are intentionally
  approximate: start a segment when sending its text and end it before starting the
  next. Playback relies on PCM arrival order, not those markers.
- `RealtimeConnection.agent_tts_prepared` owns idle handles. `close_agent_session`,
  a worker `finally`, and the stream `finally` may all call `aclose()`; it must be
  idempotent so cancellation, client disconnect, and an empty answer never leak a
  connection.
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

- **Good**: the worker prewarms CosyVoice while LLM generation is waiting for its
  first token, then immediately sends `tts.ready` and the first `continue-task` once
  a segment arrives; later segments are sent without waiting for earlier audio.
- **Base**: an Aliyun/Qwen card returns `None` from `prepare_realtime_stream` and its
  existing realtime stream still opens its own session.
- **Bad**: waiting for `queue.get()` before opening the upstream, using one
  `run-task` per segment, treating approximate segment markers as playback framing,
  or leaving an idle prewarmed handle open after cancellation or an empty answer.

### 6. Tests Required

`apps.ai_models.tests.test_tts_adapters` — assert one CosyVoice `run-task` and one
`finish-task` for multiple segments, `continue-task` overlap with reader audio, event
type order, and `task-failed` propagation.

`config.tests.test_realtime_websocket.RealtimeWebSocketTests` — assert prewarming
happens before the first queue wait; cancel and empty-answer paths call the prepared
handle's `aclose()`; a prewarm failure emits only `tts.error` and allows `agent.done`.

`config.tests.test_realtime_websocket.RealtimeTTSVoiceRoutingTests` — needs DB access
for grants, so it is a `TestCase`, not part of the `SimpleTestCase` suite above it.
Assert: ungranted tenant → `1025`; contradicting `providerCode` → `1025`; absent
`providerCode` → `tts.ready` + `tts.done` with no `tts.error`.

### 7. Wrong vs Correct

#### Wrong

```python
first_segment = await queue.get()
bundle = await _prepare_agent_tts(...)  # handshake now delays first audio
```

#### Correct

```python
bundle, error_key = await _prepare_agent_tts(...)
first_segment = await queue.get()
if first_segment is not None and bundle is None:
    await _send_realtime_error(send, 'tts.error', command_id, error_key)
    return  # LLM task continues to agent.done
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
| Binding survives the card grant but the voice was un-ticked in `selected` mode, or belongs to another company | same fallback — `resolve_device_tts_voice` re-checks the full two-level predicate, not just the card |
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
    return tts_services.get_default_tts_voice(provider)   # platform scope, may be unauthorized
return voice                                              # binding never re-checked
```

> A platform-scope twin of this helper used to live in `services/tts.py` as
> `get_effective_tts_voice_for_tenant`, reading `TenantTTSSettings.default_voice`
> with no grant check at all. It was deleted once its last caller went away —
> do not reintroduce it. The only company-scope resolver is
> `tts_authorization.get_effective_tts_voice_for_tenant`.

#### Correct

```python
return tts_auth.resolve_device_tts_voice(device)
```

---

## Scenario: Runtime-config push after an authorization change

### 1. Scope / Trigger

- Trigger: changing a card grant (including its `grant_mode` or its per-voice ticks),
  a card's `public_config`, the company default voice, a voice's `owner_tenant`, or a
  provider/voice's active/visible flags.
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
| Voice-tick-only change (`grant_mode == 'selected'`) | same single tenant-level event — the authorization PUT publishes once at the end of its transaction, not per voice |

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



---

## Scenario: Lossless agent TTS text filtering and CosyVoice task limits

### 1. Scope / Trigger

- Trigger: changing intelligent-agent TTS filter fields, LLM-delta segmentation,
  browser reply playback, or CosyVoice duplex streaming.
- The text sent upstream must equal the LLM answer with **only** the three
  page-configured transformations applied. Markdown removal, whitespace collapse,
  list-number removal, punctuation insertion, and hard length splitting are forbidden.

### 2. Signatures

```python
# AgentApplication DB / REST serializer
tts_filter_punctuation: CharField(max_length=64, default='')
tts_filter_emoji: BooleanField(default=True)
tts_filter_exclude_patterns: JSONField(default=list)

TTSStreamingTextProcessor(
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
)
feed(text: str) -> list[str]
finish() -> list[str]

validate_cosyvoice_task_text(text: str, sent_characters: int = 0) -> int
```

The REST fields are `ttsFilterPunctuation`, `ttsFilterEmoji`, and
`ttsFilterExcludePatterns`. Published runtime snapshots keep the corresponding
snake-case keys.

### 3. Contracts

- `ttsFilterPunctuation` is a literal set of characters, not a regular expression.
  Whitespace is significant (`trim_whitespace=False`), duplicate characters are
  removed in first-seen order, and empty means no punctuation removal.
- `ttsFilterExcludePatterns` contains literal strings. Matching is global, ordered,
  and stateful across arbitrary LLM delta boundaries. Duplicate entries are removed
  after trimming page input.
- Removing a character or literal must preserve its source boundary metadata. For
  example, filtering `\n` may remove that character from speech but must still allow
  the preceding list item to be emitted as a separate segment.
- Segments are emitted only at source characters in
  `。！？!?；;，,：:、\r\n`; the boundary character remains in the emitted text unless
  the page explicitly filters it. `''.join(segments)` must equal the filtered answer.
- Browser streaming reply playback applies this processor once to raw LLM deltas,
  then calls `playRealtimeTts` without forwarding the three filter fields. The backend
  receives already-filtered segments and must not apply the rules a second time.
- Backend agent playback applies one processor to the complete delta stream and calls
  `finish()` exactly once. Empty output produces no TTS request.
- One CosyVoice answer uses one `run-task`, zero or more exact `continue-task` texts,
  and one `finish-task`; PCM is forwarded as received. A prewarmed task older than
  20 seconds is closed and rebuilt only after the first real text is available.
- Provider guards are 20,000 characters per `continue-task`, 200,000 cumulative
  characters per task, and at most 23 seconds between consecutive text sends.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| `ttsFilterPunctuation` exceeds 64 characters | HTTP 400: `TTS 过滤标点不能超过 64 个字符` |
| More than 20 exclusion strings | HTTP 400: `TTS 排除文本最多 20 条` |
| Exclusion is blank or exceeds 120 characters | HTTP 400 with the field-specific message |
| `continue-task` text exceeds 20,000 characters | fail before provider send with explicit runtime error |
| Cumulative task text exceeds 200,000 characters | fail before provider send with explicit runtime error |
| Consecutive sends are more than 23 seconds apart | abort the task; never send fake keepalive text |
| Filter rules remove the whole answer | no upstream synthesis request; normal agent completion remains valid |

### 5. Good/Base/Bad Cases

- **Good**: `球形LED显示屏\n内球幕LED显示屏` becomes two upstream segments whose
  concatenation is exactly the original text when newline filtering is disabled.
- **Base**: an empty punctuation field and no exclusions preserve every LLM character;
  emoji filtering follows the saved boolean only.
- **Bad**: converting Markdown to plain text, collapsing `\r\n` to spaces, flushing a
  segment because it reached an arbitrary character count, or re-filtering a browser
  segment in the backend. Each silently changes what the user hears.

### 6. Tests Required

- `apps.ai_models.tests.test_tts_api`: identity without page rules; literal exclusion
  across delta boundaries; emoji/punctuation combinations; filtered-boundary
  preservation; empty output; 20,000/200,000-character failures; 23-second send guard;
  stale prewarm close/rebuild; one-task protocol and PCM forwarding.
- `config.tests.test_realtime_websocket`: concatenate all `tts.segment` payload texts
  and compare with the expected filtered LLM answer; assert `agent.done` after empty
  filtered output and after prewarm failure.
- Frontend build/type-check plus browser smoke: stream several raw deltas through the
  page processor, confirm the displayed answer is unchanged, transmitted segment
  concatenation equals the configured filtered answer, PCM plays, and interruption
  resets processor state.

### 7. Wrong vs Correct

#### Wrong

```python
text = strip_markdown_for_tts(text)
text = re.sub(r'\s+', ' ', text).strip()
return hard_split(text, max_length=80)
```

#### Correct

```python
processor = TTSStreamingTextProcessor(
    filter_punctuation=published_config['tts_filter_punctuation'],
    filter_emoji=published_config['tts_filter_emoji'],
    exclude_patterns=published_config['tts_filter_exclude_patterns'],
)
for delta in llm_deltas:
    for segment in processor.feed(delta):
        await queue.put(segment)
for segment in processor.finish():
    await queue.put(segment)
```