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


def _normalize_api_protocol(value: str | None) -> str:
    return 'responses' if value == 'responses' else 'chat_completions'


def get_llm_api_protocol(provider_or_config) -> str:
    if isinstance(provider_or_config, dict):
        return _normalize_api_protocol(provider_or_config.get('apiProtocol'))
    return _normalize_api_protocol(getattr(provider_or_config, 'api_protocol', None))


def build_llm_api_url(raw_url: str, api_protocol: str = 'chat_completions') -> str:
    api_url = raw_url.rstrip('/')
    protocol = _normalize_api_protocol(api_protocol)
    if protocol == 'responses':
        if api_url.endswith('/responses'):
            return api_url
        if api_url.endswith('/chat/completions'):
            return f'{api_url[:-len("/chat/completions")]}/responses'
        if api_url.endswith('/openai'):
            return f'{api_url}/v1/responses'
        if api_url.endswith('/v1'):
            return f'{api_url}/responses'
        return f'{api_url}/responses'
    if api_url.endswith('/responses'):
        return f'{api_url[:-len("/responses")]}/chat/completions'
    if api_url.endswith('/chat/completions'):
        return api_url
    if api_url.endswith('/openai'):
        return f'{api_url}/v1/chat/completions'
    if api_url.endswith('/v1'):
        return f'{api_url}/chat/completions'
    return f'{api_url}/chat/completions'

def _responses_input(messages: list[dict]) -> list[dict]:
    if not any(message.get('role') == 'system' for message in messages if isinstance(message, dict)):
        return messages
    return [
        {**message, 'role': 'developer'} if isinstance(message, dict) and message.get('role') == 'system' else message
        for message in messages
    ]




def _responses_tools(tools: list[dict] | None) -> list[dict]:
    response_tools = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        function = tool.get('function')
        if tool.get('type') == 'function' and isinstance(function, dict):
            converted = {'type': 'function'}
            for key in ('name', 'description', 'parameters'):
                if key in function:
                    converted[key] = function[key]
            response_tools.append(converted)
        else:
            response_tools.append(dict(tool))
    return response_tools


def build_llm_request_payload(
    *,
    model_name: str,
    messages: list[dict],
    stream: bool,
    temperature: float,
    max_tokens: int | None,
    max_tokens_unlimited: bool = False,
    enable_web_search: bool = False,
    api_protocol: str = 'chat_completions',
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
) -> dict:
    protocol = _normalize_api_protocol(api_protocol)
    payload = {'model': model_name, 'stream': stream, 'temperature': temperature}
    if protocol == 'responses':
        payload['input'] = _responses_input(messages)
        if not max_tokens_unlimited and max_tokens is not None:
            payload['max_output_tokens'] = max_tokens
        response_tools = _responses_tools(tools)
        if enable_web_search:
            response_tools.append({'type': 'web_search'})
        if response_tools:
            payload['tools'] = response_tools
        if tool_choice is not None:
            payload['tool_choice'] = tool_choice
        return payload

    payload['messages'] = messages
    if not max_tokens_unlimited and max_tokens is not None:
        payload['max_tokens'] = max_tokens
    if tools:
        payload['tools'] = tools
    if tool_choice is not None:
        payload['tool_choice'] = tool_choice
    if enable_web_search:
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
    api_protocol = get_llm_api_protocol(provider)
    api_url = build_llm_api_url(provider.api_base_url, api_protocol)
    response = None
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                api_url,
                json=build_llm_request_payload(
                    model_name=model.name,
                    messages=messages,
                    stream=False,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    enable_web_search=model.enable_web_search,
                    api_protocol=api_protocol,
                ),
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

    error_message = extract_llm_error_message(payload)
    if error_message:
        raise RuntimeError(error_message[:200])

    text = extract_llm_completion_text(payload, api_protocol=api_protocol)
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
    max_tokens: int | None = 1000,
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
            'apiProtocol': get_llm_api_protocol(provider),
            'enableWebSearch': model.enable_web_search,
        }
    api_protocol = get_llm_api_protocol(model_config)
    api_url = build_llm_api_url(model_config['apiBaseUrl'], api_protocol)
    payload = build_llm_request_payload(
        model_name=model_config['name'],
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        max_tokens_unlimited=max_tokens is None,
        enable_web_search=bool(model_config.get('enableWebSearch')),
        api_protocol=api_protocol,
    )
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
                error_message = extract_llm_error_message(chunk)
                if error_message:
                    raise RuntimeError(error_message[:200])
                text = extract_llm_stream_delta(chunk, api_protocol=api_protocol)
                if text:
                    yield text

            if not saw_sse_data and buffered_plain_lines:
                raw_text = ''.join(buffered_plain_lines).strip()
                try:
                    body = json.loads(raw_text)
                except json.JSONDecodeError:
                    body = None
                if isinstance(body, dict):
                    error_message = extract_llm_error_message(body)
                    if error_message:
                        raise RuntimeError(error_message[:200])
                    text = extract_llm_completion_text(body, api_protocol=api_protocol)
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
    """Stream an LLM completion while preserving the caller's text/tool event contract."""
    api_protocol = get_llm_api_protocol(model_config)
    api_url = build_llm_api_url(model_config['apiBaseUrl'], api_protocol)
    payload = build_llm_request_payload(
        model_name=model_config['name'],
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_web_search=bool(model_config.get('enableWebSearch')),
        api_protocol=api_protocol,
        tools=tools,
        tool_choice=tool_choice,
    )

    merged_tool_calls: dict[int, dict] = {}
    response_tool_calls: dict[str, dict] = {}
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
                error_message = extract_llm_error_message(chunk)
                if error_message:
                    raise RuntimeError(error_message[:200])
                text = extract_llm_stream_delta(chunk, api_protocol=api_protocol)
                if text:
                    yield {'type': 'delta', 'text': text}
                if api_protocol == 'responses':
                    for call in extract_responses_tool_calls(chunk):
                        response_tool_calls[call['id']] = call
                else:
                    choices = chunk.get('choices')
                    if not isinstance(choices, list) or not choices:
                        continue
                    first_choice = choices[0] if isinstance(choices[0], dict) else {}
                    delta = first_choice.get('delta') if isinstance(first_choice.get('delta'), dict) else {}
                    _merge_tool_calls_delta(merged_tool_calls, delta.get('tool_calls'))

            tool_calls = list(response_tool_calls.values()) if api_protocol == 'responses' else list(merged_tool_calls.values())
            if tool_calls:
                yield {'type': 'tool_calls', 'tool_calls': tool_calls}
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


def _extract_responses_completion_text(payload: dict) -> str:
    response = payload.get('response') if isinstance(payload.get('response'), dict) else payload
    output_text = response.get('output_text')
    text = _coerce_openai_content_to_text(output_text)
    if text:
        return text
    output = response.get('output')
    if not isinstance(output, list):
        return ''
    chunks = []
    for item in output:
        if not isinstance(item, dict):
            continue
        chunks.append(_coerce_openai_content_to_text(item.get('content')))
    return ''.join(chunks)


def extract_llm_completion_text(payload: dict, *, api_protocol: str = 'chat_completions') -> str:
    if _normalize_api_protocol(api_protocol) == 'responses':
        return _extract_responses_completion_text(payload)
    return _extract_openai_completion_text(payload)


def extract_llm_stream_delta(payload: dict, *, api_protocol: str = 'chat_completions') -> str:
    if _normalize_api_protocol(api_protocol) != 'responses':
        return _extract_openai_completion_delta(payload)
    if payload.get('type') == 'response.output_text.delta':
        return _coerce_openai_content_to_text(payload.get('delta'))
    return ''


def extract_responses_tool_calls(payload: dict) -> list[dict]:
    response = payload.get('response') if isinstance(payload.get('response'), dict) else payload
    items = []
    if payload.get('type') == 'response.output_item.done' and isinstance(payload.get('item'), dict):
        items.append(payload['item'])
    output = response.get('output') if isinstance(response, dict) else None
    if isinstance(output, list):
        items.extend(output)
    calls = []
    for item in items:
        if not isinstance(item, dict) or item.get('type') != 'function_call':
            continue
        name = item.get('name')
        arguments = item.get('arguments')
        call_id = item.get('call_id') or item.get('id')
        if not isinstance(name, str) or not isinstance(arguments, str) or not isinstance(call_id, str):
            continue
        calls.append({
            'id': call_id,
            'type': 'function',
            'function': {'name': name, 'arguments': arguments},
        })
    return calls


def _extract_openai_error_message(payload: dict) -> str:
    error = payload.get('error')
    if isinstance(error, dict):
        message = error.get('message')
        if isinstance(message, str):
            return message
    return ''


def extract_llm_error_message(payload: dict) -> str:
    return _extract_openai_error_message(payload)


def _test_summary(*, success: bool, message: str, start: float) -> dict:
    return {
        'success': success,
        'message': message,
        'latencyMs': int((time.monotonic() - start) * 1000),
        'testedAt': timezone.localtime(timezone.now()).isoformat(),
    }


def run_llm_model_test(*, model: LLMModel, settings: LLMTestSettings | None = None) -> dict:
    """Run one protocol-aware test request and return a safe summary."""
    if settings is None:
        settings = LLMTestSettings.load()
    provider = model.provider
    api_protocol = get_llm_api_protocol(provider)
    api_url = build_llm_api_url(provider.api_base_url, api_protocol)
    payload = build_llm_request_payload(
        model_name=model.name,
        messages=[{'role': 'user', 'content': settings.test_prompt}],
        stream=False,
        temperature=0,
        max_tokens=settings.test_max_tokens,
        enable_web_search=model.enable_web_search,
        api_protocol=api_protocol,
    )
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
