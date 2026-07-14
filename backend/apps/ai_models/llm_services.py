import json
import time
import asyncio

import httpx
from django.db import models
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LLMModel, LLMTestSettings, TenantLLMSettings

_STREAM_LLM_CLIENTS: dict[int, httpx.AsyncClient] = {}


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
        payload['search_options'] = {'forced_search': True}
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


def _get_stream_llm_client() -> httpx.AsyncClient:
    loop_id = id(asyncio.get_running_loop())
    client = _STREAM_LLM_CLIENTS.get(loop_id)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30),
        )
        _STREAM_LLM_CLIENTS[loop_id] = client
    return client


async def stream_llm_chat_completion(
    *,
    model: LLMModel | None = None,
    model_config: dict | None = None,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1000,
    timeout: int = 120,
):
    if model_config is None:
        if model is None:
            raise RuntimeError('LLM 模型未配置')
        provider = model.provider
        model_config = {
            'name': model.name,
            'apiBaseUrl': provider.api_base_url,
            'apiKey': provider.api_key,
            'enableWebSearch': model.enable_web_search,
        }
    api_url = _build_chat_completions_url(model_config['apiBaseUrl'])
    payload = {
        'model': model_config['name'],
        'messages': messages,
        'stream': True,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if model_config.get('enableWebSearch'):
        payload['enable_search'] = True
        payload['search_options'] = {'forced_search': True}
    try:
        client = _get_stream_llm_client()
        async with client.stream(
            'POST',
            api_url,
            json=payload,
            headers={
                'Authorization': f"Bearer {model_config['apiKey']}",
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json',
            },
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f'LLM 请求失败 (HTTP {response.status_code})')

            saw_sse_data = False
            buffered_plain_lines: list[str] = []
            async for line in response.aiter_lines():
                if not line:
                    continue
                data_str = _parse_sse_data_line(line)
                if data_str is None:
                    if not saw_sse_data:
                        buffered_plain_lines.append(line)
                    continue

                saw_sse_data = True
                buffered_plain_lines.clear()
                if data_str.strip() == '[DONE]':
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                error_message = _extract_openai_error_message(chunk)
                if error_message:
                    raise RuntimeError(error_message[:200])
                text = _extract_openai_completion_delta(chunk)
                if text:
                    yield text

            if not saw_sse_data and buffered_plain_lines:
                raw_text = ''.join(buffered_plain_lines).strip()
                try:
                    body = json.loads(raw_text)
                except json.JSONDecodeError:
                    body = None
                if isinstance(body, dict):
                    error_message = _extract_openai_error_message(body)
                    if error_message:
                        raise RuntimeError(error_message[:200])
                    text = _extract_openai_completion_text(body)
                    if text:
                        yield text
    except httpx.TimeoutException as exc:
        raise RuntimeError('LLM 请求超时') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError('LLM 连接失败') from exc


async def stream_llm_chat_completion_with_tools(
    *,
    model_config: dict,
    messages: list[dict],
    tools: list[dict],
    tool_choice: str = 'auto',
    temperature: float = 0.3,
    max_tokens: int = 500,
    timeout: int = 30,
):
    """Stream an OpenAI-compatible chat completion with function tools.

    Yields event dicts:
        - {'type': 'delta', 'text': str}        # assistant content delta
        - {'type': 'tool_calls', 'tool_calls': list[dict]}  # merged tool calls at finish
        - {'type': 'done'}                      # stream finished
    """
    api_url = _build_chat_completions_url(model_config['apiBaseUrl'])
    payload = {
        'model': model_config['name'],
        'messages': messages,
        'stream': True,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'tools': tools,
        'tool_choice': tool_choice,
    }
    if model_config.get('enableWebSearch'):
        payload['enable_search'] = True
        payload['search_options'] = {'forced_search': True}

    merged_tool_calls: dict[int, dict] = {}
    try:
        client = _get_stream_llm_client()
        async with client.stream(
            'POST',
            api_url,
            json=payload,
            headers={
                'Authorization': f"Bearer {model_config['apiKey']}",
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json',
            },
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f'LLM 请求失败 (HTTP {response.status_code})')

            async for line in response.aiter_lines():
                if not line:
                    continue
                data_str = _parse_sse_data_line(line)
                if data_str is None:
                    continue
                if data_str.strip() == '[DONE]':
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                error_message = _extract_openai_error_message(chunk)
                if error_message:
                    raise RuntimeError(error_message[:200])
                choices = chunk.get('choices')
                if not isinstance(choices, list) or not choices:
                    continue
                first_choice = choices[0] if isinstance(choices[0], dict) else {}
                delta = first_choice.get('delta') if isinstance(first_choice.get('delta'), dict) else {}
                content = _coerce_openai_content_to_text(delta.get('content'))
                if content:
                    yield {'type': 'delta', 'text': content}
                _merge_tool_calls_delta(merged_tool_calls, delta.get('tool_calls'))

            if merged_tool_calls:
                yield {'type': 'tool_calls', 'tool_calls': list(merged_tool_calls.values())}
            yield {'type': 'done'}
    except httpx.TimeoutException as exc:
        raise RuntimeError('LLM 请求超时') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError('LLM 连接失败') from exc


def _merge_tool_calls_delta(merged: dict[int, dict], delta_calls: list[dict] | None) -> None:
    """Accumulate streaming tool_calls deltas into complete tool_call objects."""
    if not isinstance(delta_calls, list):
        return
    for call in delta_calls:
        if not isinstance(call, dict):
            continue
        index = call.get('index')
        if index is None:
            index = len(merged)
        index = int(index)
        current = merged.setdefault(
            index,
            {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}},
        )
        if call.get('id'):
            current['id'] = call['id']
        if call.get('type'):
            current['type'] = call['type']
        function = call.get('function')
        if isinstance(function, dict):
            name = function.get('name')
            if isinstance(name, str) and name:
                current['function']['name'] = current['function']['name'] + name if current['function']['name'] else name
            arguments = function.get('arguments')
            if isinstance(arguments, str):
                current['function']['arguments'] += arguments


def _parse_sse_data_line(line: str) -> str | None:
    if line.startswith('data:'):
        return line[5:].strip()
    return None


def _extract_openai_completion_delta(payload: dict) -> str:
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''
    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = first_choice.get('delta')
    if isinstance(delta, dict):
        content = _coerce_openai_content_to_text(delta.get('content'))
        if content:
            return content
    return _coerce_openai_content_to_text(first_choice.get('text'))


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
