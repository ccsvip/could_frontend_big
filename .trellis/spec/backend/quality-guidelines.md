# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### 1. Superuser-Only Admin API Guard

Platform-level admin APIs must use a strict `IsSuperUser` permission class that checks `request.user.is_superuser`, NOT `is_staff`. This prevents company admins, employees, and non-superuser staff accounts from accessing platform management endpoints.

```python
# backend/apps/app_updates/views.py (reference)
from rest_framework.permissions import BasePermission

class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
```

**Why**: `is_staff=True` is used for Django Admin access across many user types. Using it as the sole check for platform-level APIs would leak management capabilities to company-level users.

**Apply to**: All platform-level CRUD APIs (release management, global config, system settings). Company-scoped APIs use tenant permission codes instead.

**Forbidden**:
```python
# ❌ Wrong — is_staff is too broad, lets company admins through
permission_classes = [IsAdminUser]  # IsAdminUser checks is_staff
```

### 2. Secret Loading from Environment

Sensitive cryptographic keys must be loaded from environment variables or mounted secret files, never hardcoded or checked into version control. Use a Base64-encoded PEM variable as primary and a file path as fallback.

```python
# backend/apps/app_updates/signing.py (reference)
import base64
import os
from django.conf import settings

def _load_private_key() -> bytes:
    encoded = settings.APP_UPDATE_PRIVATE_KEY_BASE64
    if encoded:
        return base64.b64decode(encoded)
    path = settings.APP_UPDATE_PRIVATE_KEY_FILE
    if path and os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return None  # caller handles None with clear 503
```

**Why**: Keys checked into git are exposed to every developer with repo access. Env-based loading allows per-deployment keys without code changes.

### 3. Deterministic API Response Signing

When signing API responses for client verification (e.g., OTA update payloads), construct the signing payload as a deterministic UTF-8 string with fields in a fixed order separated by newlines. Do NOT use serializers, JSON, or delimiters that could vary across language runtimes.

```python
# backend/apps/app_updates/signing.py (reference)
SIGNING_FIELDS = [
    "downloadUrl", "fileSize", "sha256",
    "versionName", "versionCode", "packageName", "expiresAt"
]

def build_signing_payload(release_dict: dict, expires_at: str) -> bytes:
    lines = "\n".join(
        f"{field}={release_dict[field]}"
        for field in SIGNING_FIELDS
    ) + f"\nexpiresAt={expires_at}"
    return lines.encode("utf-8")
```

**Why**: JSON serialization ordering varies by runtime and library versions. Newline-separated `key=value` pairs are trivially reproducible on all platforms (Android, iOS, backend).

### 4. Range Request File Download

When serving file downloads that may be large (APK, firmware, media), support HTTP Range requests for resume capability. Return proper status codes and headers per the HTTP spec.

| Condition | Status | Headers |
|-----------|--------|---------|
| No `Range` header | `200` | `Content-Length`, `Content-Type`, `ETag` (SHA-256) |
| Valid single `Range: bytes=N-M` | `206` | `Content-Length`, `Content-Range: bytes N-M/T`, `Accept-Ranges: bytes` |
| Invalid/unsatisfiable Range | `416` | `Content-Range: bytes */T` |

**Why**: Large APK downloads may be interrupted on mobile networks. Range support enables resume without re-downloading the entire file.

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)

## Realtime ASR Automatic Language Detection

### 1. Scope / Trigger

The DashScope Qwen-ASR Realtime `session.update` payload crosses device, backend WebSocket, and external-provider boundaries. Any change to `input_audio_transcription.language` changes the transcription contract for every spoken language.

### 2. Signatures

- `apps.ai_models.services.asr._transcription_session_update_event(sample_rate, config)` for device PCM transcription.
- `apps.ai_models.realtime_asr._session_update_event(...)` for regular and agent unified-realtime ASR sessions.
- `apps.ai_models.services.asr.test_asr_connection()` for the administrative connectivity probe.

### 3. Contract

Send automatic source-language detection as an empty transcription configuration; omit `language` rather than sending an `auto` value:

```python
'input_audio_transcription': {}
```

Qwen-ASR documents `language` as optional and instructs callers with an unknown or mixed source language not to set it. Do not remove `input_audio_transcription`; keep the object as the recognition configuration boundary.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Language is unknown or mixed | Omit `input_audio_transcription.language`; the provider detects it. |
| A fixed source language is known and intentionally required | Set a documented language code only after an explicit product decision. |
| A developer proposes `language: 'auto'` | Reject it; this is not the documented automatic-detection contract. |
| The ASR configuration object is removed | Do not do this without confirming provider behavior and the realtime transcription contract. |

### 5. Good / Base / Bad Cases

- Good: English, Chinese, Japanese, or mixed audio uses `input_audio_transcription: {}` and the provider chooses the source language.
- Base: VAD thresholds and sample rate remain unchanged when only language selection changes.
- Bad: A shared ASR session builder hardcodes `{'language': 'zh'}`, which biases every caller toward Chinese recognition.

### 6. Tests Required

- `apps.ai_models.tests.test_asr_api`: assert that the administrative ASR probe and the device PCM session builder send `{}`.
- `apps.ai_models.tests.test_asr_realtime`: assert that the unified WebSocket upstream receives `{}` after `asr.session.start`.
- Run `docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api apps.ai_models.tests.test_asr_realtime --keepdb`.

### 7. Wrong vs Correct

#### Wrong

```python
'input_audio_transcription': {'language': 'zh'}
```

#### Correct

```python
'input_audio_transcription': {}
```
