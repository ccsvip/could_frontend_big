from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx
from django.db import transaction

from apps.ai_models.credential_crypto import decrypt_credential
from apps.ai_models.models import CosyVoiceProfile, CosyVoiceSettings, TTSProvider, TTSVoice
from apps.ai_models.services.tts import DEFAULT_TEST_TEXT, EffectiveTTSConfig


COSYVOICE_PROVIDER_CODE = 'cosyvoice'
COSYVOICE_MODEL = 'cosyvoice-v3.5-plus'
COSYVOICE_WEBSOCKET_URL_ERROR = (
    'CosyVoice WebSocket 地址必须为北京地域端点（wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference）。'
)
COSYVOICE_CUSTOMIZATION_URL_ERROR = (
    'CosyVoice 定制 API 地址必须为北京地域端点（https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization）。'
)
_COSYVOICE_WORKSPACE_ID_PATTERN = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'


@dataclass(slots=True)
class CosyVoiceCustomizationError(Exception):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def _is_valid_cosyvoice_workspace_endpoint(value: str, *, scheme: str, path: str) -> bool:
    pattern = (
        rf'{re.escape(scheme)}://{_COSYVOICE_WORKSPACE_ID_PATTERN}'
        rf'\.cn-beijing\.maas\.aliyuncs\.com{re.escape(path)}'
    )
    return re.fullmatch(pattern, value) is not None


def is_valid_cosyvoice_websocket_url(value: str) -> bool:
    return _is_valid_cosyvoice_workspace_endpoint(
        value,
        scheme='wss',
        path='/api-ws/v1/inference',
    )


def is_valid_cosyvoice_customization_url(value: str) -> bool:
    return _is_valid_cosyvoice_workspace_endpoint(
        value,
        scheme='https',
        path='/api/v1/services/audio/tts/customization',
    )


def get_cosyvoice_settings() -> CosyVoiceSettings:
    provider, _ = TTSProvider.objects.get_or_create(
        code=COSYVOICE_PROVIDER_CODE,
        defaults={'name': 'CosyVoice', 'model': COSYVOICE_MODEL, 'is_active': True},
    )
    settings_obj, _ = CosyVoiceSettings.objects.get_or_create(
        provider=provider,
        defaults={'default_test_text': DEFAULT_TEST_TEXT, 'is_active': True},
    )
    return settings_obj


def get_effective_cosyvoice_tts_config(settings_obj: CosyVoiceSettings | None = None) -> EffectiveTTSConfig:
    settings_obj = settings_obj or get_cosyvoice_settings()
    websocket_url = settings_obj.websocket_url
    if websocket_url and not is_valid_cosyvoice_websocket_url(websocket_url):
        raise CosyVoiceCustomizationError(COSYVOICE_WEBSOCKET_URL_ERROR, status_code=400)
    return EffectiveTTSConfig(
        provider=settings_obj.provider,
        provider_code=COSYVOICE_PROVIDER_CODE,
        api_key=decrypt_credential(settings_obj.api_key_encrypted),
        base_url=websocket_url,
        model=COSYVOICE_MODEL,
        sample_rate=24000,
        tts_session_config={},
        default_test_text=settings_obj.default_test_text.strip() or DEFAULT_TEST_TEXT,
        is_active=bool(settings_obj.is_active),
        updated_at=settings_obj.updated_at,
    )


def is_cosyvoice_configured(settings_obj: CosyVoiceSettings | None = None) -> bool:
    settings_obj = settings_obj or get_cosyvoice_settings()
    return bool(
        settings_obj.is_active
        and settings_obj.api_key_encrypted
        and is_valid_cosyvoice_websocket_url(settings_obj.websocket_url)
        and is_valid_cosyvoice_customization_url(settings_obj.customization_url)
    )


def _voice_prefix(display_name: str) -> str:
    prefix = re.sub(r'[^A-Za-z0-9]', '', display_name)[:10]
    return prefix if len(prefix) >= 2 else f'cv{TTSVoice.objects.filter(provider__code=COSYVOICE_PROVIDER_CODE).count() + 1}'


def _response_message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return f'{fallback}（HTTP {response.status_code}）'
    if isinstance(body, dict):
        error = body.get('error')
        message = error.get('message') if isinstance(error, dict) else body.get('message')
        if message:
            return f'{fallback}（{str(message)[:200]}）'
    return f'{fallback}（HTTP {response.status_code}）'


def _post_customization(settings_obj: CosyVoiceSettings, payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = settings_obj.customization_url
    api_key = decrypt_credential(settings_obj.api_key_encrypted)
    if not endpoint or not api_key:
        raise CosyVoiceCustomizationError('请先配置 CosyVoice 定制 API 地址和 API Key。', status_code=400)
    if not is_valid_cosyvoice_customization_url(endpoint):
        raise CosyVoiceCustomizationError(COSYVOICE_CUSTOMIZATION_URL_ERROR, status_code=400)
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
            )
    except httpx.TimeoutException as exc:
        raise CosyVoiceCustomizationError('CosyVoice 定制请求超时。') from exc
    except httpx.HTTPError as exc:
        raise CosyVoiceCustomizationError('CosyVoice 定制服务不可达。') from exc
    if response.is_error:
        raise CosyVoiceCustomizationError(_response_message(response, 'CosyVoice 定制请求失败'))
    try:
        body = response.json()
    except ValueError as exc:
        raise CosyVoiceCustomizationError('CosyVoice 定制服务返回了无效响应。') from exc
    if not isinstance(body, dict):
        raise CosyVoiceCustomizationError('CosyVoice 定制服务返回了无效响应。')
    return body


def _remote_voice_id(payload: dict[str, Any]) -> str:
    output = payload.get('output')
    if isinstance(output, dict):
        voice_id = output.get('voice_id')
        if isinstance(voice_id, str) and voice_id:
            return voice_id
    raise CosyVoiceCustomizationError('CosyVoice 上游未返回音色标识。')


def _create_voice(
    *,
    settings_obj: CosyVoiceSettings,
    display_name: str,
    source_type: str,
    source_audio_url: str = '',
    description: str = '',
    avatar_path: str = '',
    language: str = '',
) -> TTSVoice:
    if not settings_obj.is_active:
        raise CosyVoiceCustomizationError('请先启用 CosyVoice。', status_code=400)
    if not display_name.strip():
        raise CosyVoiceCustomizationError('请填写音色名称。', status_code=400)

    prefix = _voice_prefix(display_name)
    if source_type == CosyVoiceProfile.SOURCE_ENROLL:
        if not source_audio_url.startswith('https://'):
            raise CosyVoiceCustomizationError('参考音频必须是可访问的 HTTPS URL。', status_code=400)
        input_payload = {'target_model': COSYVOICE_MODEL, 'prefix': prefix, 'url': source_audio_url}
    else:
        if not description.strip():
            raise CosyVoiceCustomizationError('请填写音色描述。', status_code=400)
        if language not in {'zh', 'en'}:
            raise CosyVoiceCustomizationError('音色设计仅支持中文或英文。', status_code=400)
        input_payload = {
            'target_model': COSYVOICE_MODEL,
            'prefix': prefix,
            'voice_prompt': description,
            'preview_text': (settings_obj.default_test_text.strip() or DEFAULT_TEST_TEXT)[:200],
            'language_hints': [language],
        }

    payload = _post_customization(
        settings_obj,
        {'model': 'voice-enrollment', 'input': {'action': 'create_voice', **input_payload}},
    )
    remote_voice_id = _remote_voice_id(payload)
    with transaction.atomic():
        voice = TTSVoice.objects.create(
            provider=settings_obj.provider,
            voice_code=remote_voice_id,
            display_name=display_name.strip(),
            avatar_path=avatar_path,
            sort_order=TTSVoice.objects.filter(provider=settings_obj.provider).count(),
        )
        CosyVoiceProfile.objects.create(
            voice=voice,
            source_type=source_type,
            source_audio_url=source_audio_url,
            description=description.strip(),
            language=language,
        )
    return voice


def enroll_cosyvoice_voice(
    *, settings_obj: CosyVoiceSettings, display_name: str, source_audio_url: str, avatar_path: str = ''
) -> TTSVoice:
    return _create_voice(
        settings_obj=settings_obj,
        display_name=display_name,
        source_type=CosyVoiceProfile.SOURCE_ENROLL,
        source_audio_url=source_audio_url,
        avatar_path=avatar_path,
    )


def design_cosyvoice_voice(
    *, settings_obj: CosyVoiceSettings, display_name: str, description: str, language: str, avatar_path: str = ''
) -> TTSVoice:
    return _create_voice(
        settings_obj=settings_obj,
        display_name=display_name,
        source_type=CosyVoiceProfile.SOURCE_DESIGN,
        description=description,
        language=language,
        avatar_path=avatar_path,
    )

def delete_cosyvoice_remote_voice(*, voice: TTSVoice) -> None:
    try:
        profile = voice.cosyvoice_profile
    except CosyVoiceProfile.DoesNotExist:
        raise CosyVoiceCustomizationError('该音色不是 CosyVoice 自定义音色。', status_code=400)
    _post_customization(
        get_cosyvoice_settings(),
        {'model': 'voice-enrollment', 'input': {'action': 'delete_voice', 'voice_id': voice.voice_code}},
    )
