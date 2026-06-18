import time

import httpx
from django.db import models
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LLMModel, LLMTestSettings, TenantLLMSettings


def mask_api_key(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '****'
    return f'{value[:3]}...{value[-4:]}'


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


def get_effective_llm_model_for_tenant(tenant, model_id):
    return get_effective_llm_models_for_tenant(tenant).filter(id=model_id).first()


def get_tenant_llm_settings(tenant):
    if tenant is None:
        return None
    settings, _ = TenantLLMSettings.objects.get_or_create(tenant=tenant)
    return settings


def is_llm_model_effective_for_tenant(tenant, model) -> bool:
    if tenant is None or model is None:
        return False
    return get_effective_llm_models_for_tenant(tenant).filter(id=model.id).exists()


def llm_model_has_usage(model) -> bool:
    if model is None:
        return False
    return (
        model.tenant_grants.exists()
        or model.tenant_default_settings.exists()
        or model.conversations.exists()
        or model.agent_applications.exists()
    )


def llm_model_has_active_company_authorization(model) -> bool:
    if model is None:
        return False
    return model.tenant_grants.filter(is_active=True).exists()


def llm_provider_has_active_company_authorization(provider) -> bool:
    if provider is None:
        return False
    return LLMModel.objects.filter(provider=provider, tenant_grants__is_active=True).exists()


def llm_provider_has_usage(provider) -> bool:
    if provider is None:
        return False
    return LLMModel.objects.filter(provider=provider).filter(
        models.Q(tenant_grants__isnull=False)
        | models.Q(tenant_default_settings__isnull=False)
        | models.Q(conversations__isnull=False)
        | models.Q(agent_applications__isnull=False)
    ).exists()


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


def _build_chat_completions_url(raw_url: str) -> str:
    api_url = raw_url.rstrip('/')
    if api_url.endswith('/chat/completions'):
        return api_url
    if api_url.endswith('/openai'):
        return f'{api_url}/v1/chat/completions'
    if api_url.endswith('/v1'):
        return f'{api_url}/chat/completions'
    return f'{api_url}/chat/completions'


def _with_model_search_param(model: LLMModel, payload: dict) -> dict:
    if model.enable_web_search:
        payload['enable_search'] = True
    return payload


def run_llm_chat_completion(
    *,
    model: LLMModel,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1000,
    timeout: int = 120,
) -> str:
    provider = model.provider
    api_url = _build_chat_completions_url(provider.api_base_url)
    response = None
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                api_url,
                json=_with_model_search_param(model, {
                    'model': model.name,
                    'messages': messages,
                    'stream': False,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                }),
                headers={
                    'Authorization': f'Bearer {provider.api_key}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError('LLM 请求超时') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError('LLM 连接失败') from exc

    if response.status_code != 200:
        raise RuntimeError(f'LLM 请求失败 (HTTP {response.status_code})')

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError('LLM 响应不是有效 JSON') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('LLM 响应格式错误')

    error_message = _extract_openai_error_message(payload)
    if error_message:
        raise RuntimeError(error_message[:200])

    text = _extract_openai_completion_text(payload)
    if not text:
        raise RuntimeError('LLM 响应为空')
    return text


def _extract_openai_completion_text(payload: dict) -> str:
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get('message')
    if isinstance(message, dict):
        content = _coerce_openai_content_to_text(message.get('content'))
        if content:
            return content
    return _coerce_openai_content_to_text(first_choice.get('text'))


def _coerce_openai_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get('text')
            if isinstance(text, str):
                chunks.append(text)
                continue
            inner_text = item.get('content')
            if isinstance(inner_text, str):
                chunks.append(inner_text)
        return ''.join(chunks)
    return ''


def _extract_openai_error_message(payload: dict) -> str:
    error = payload.get('error')
    if isinstance(error, dict):
        message = error.get('message')
        if isinstance(message, str):
            return message
    return ''


def _test_summary(*, success: bool, message: str, start: float) -> dict:
    return {
        'success': success,
        'message': message,
        'latencyMs': int((time.monotonic() - start) * 1000),
        'testedAt': timezone.localtime(timezone.now()).isoformat(),
    }


def run_llm_model_test(*, model: LLMModel, settings: LLMTestSettings | None = None) -> dict:
    """Run one non-streaming OpenAI-compatible test request and return a safe summary."""
    if settings is None:
        settings = LLMTestSettings.load()
    provider = model.provider
    api_url = _build_chat_completions_url(provider.api_base_url)
    payload = {
        'model': model.name,
        'messages': [{'role': 'user', 'content': settings.test_prompt}],
        'stream': False,
        'temperature': 0,
        'max_tokens': settings.test_max_tokens,
    }
    _with_model_search_param(model, payload)
    headers = {
        'Authorization': f'Bearer {provider.api_key}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    start = time.monotonic()

    try:
        with httpx.Client(timeout=settings.test_timeout_seconds) as client:
            response = client.post(api_url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return _test_summary(
            success=False,
            message=f'请求超时（{settings.test_timeout_seconds}秒）',
            start=start,
        )
    except httpx.HTTPError:
        return _test_summary(success=False, message='连接失败', start=start)

    if response.status_code == 200:
        return _test_summary(success=True, message='连接成功', start=start)

    return _test_summary(
        success=False,
        message=f'连接失败 (HTTP {response.status_code})',
        start=start,
    )
