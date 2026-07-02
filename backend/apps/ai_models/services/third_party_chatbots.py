from __future__ import annotations

import copy
import json
import re
from urllib.parse import urljoin

import httpx
from asgiref.sync import sync_to_async

from apps.ai_models.models import (
    THIRD_PARTY_CHATBOT_SCHEME_A,
    THIRD_PARTY_CHATBOT_SCHEME_B,
    TenantThirdPartyChatbotGrant,
    ThirdPartyChatbotApplication,
)


def get_effective_chatbots_for_tenant(tenant):
    if tenant is None:
        return ThirdPartyChatbotApplication.objects.none()
    return (
        ThirdPartyChatbotApplication.objects
        .select_related('provider')
        .filter(
            provider__is_active=True,
            is_active=True,
            tenant_grants__tenant=tenant,
            tenant_grants__is_active=True,
            integration__is_active=True,
        )
        .order_by('provider__sort_order', 'provider__id', 'sort_order', 'id')
        .distinct()
    )


def get_effective_chatbot_for_tenant(tenant, chatbot_id):
    return get_effective_chatbots_for_tenant(tenant).filter(id=chatbot_id).first()


def is_chatbot_effective_for_tenant(tenant, chatbot) -> bool:
    if tenant is None or chatbot is None:
        return False
    return get_effective_chatbots_for_tenant(tenant).filter(id=chatbot.id).exists()


def chatbot_has_active_company_authorization(chatbot) -> bool:
    if chatbot is None:
        return False
    return TenantThirdPartyChatbotGrant.objects.filter(chatbot=chatbot, is_active=True).exists()


def send_chatbot_message(
    chatbot: ThirdPartyChatbotApplication,
    message: str,
    *,
    conversation=None,
    timeout: int = 120,
) -> str:
    integration = getattr(chatbot, 'integration', None)
    if integration is not None:
        if not integration.is_active:
            raise RuntimeError('第三方机器人方案未启用')
        result = run_chatbot_integration_config(
            provider=chatbot.provider,
            config=integration.config or {},
            message=message,
            conversation=conversation,
            initial_variables={
                'chatbotId': chatbot.id,
                'externalApplicationId': chatbot.external_application_id,
            },
            timeout=timeout,
        )
        answer = result.get('answer')
        if answer:
            return answer
        raise RuntimeError('第三方机器人没有返回有效回复')
    raise RuntimeError('第三方机器人未绑定可用方案')


def normalize_chatbot_api_key(value: str) -> str:
    return str(value or '').strip().strip('`').strip()


SENSITIVE_KEYWORDS = ('authorization', 'api-key', 'api_key', 'apikey', 'token', 'secret', 'password', 'key')
TEMPLATE_PATTERN = re.compile(r'\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}')


class ThirdPartyChatbotIntegrationError(RuntimeError):
    def __init__(self, message: str, *, steps: list[dict] | None = None):
        super().__init__(message)
        self.steps = steps or []


def default_scheme_a_config() -> dict:
    return {
        'schemeType': THIRD_PARTY_CHATBOT_SCHEME_A,
        'steps': [
            {
                'key': 'open_chat',
                'name': '打开会话',
                'method': 'GET',
                'path': '/application/{{externalApplicationId}}/chat/open',
                'headers': [
                    {'key': 'AUTHORIZATION', 'value': '{{apiKey}}'},
                    {'key': 'Accept', 'value': 'application/json'},
                ],
                'body': {},
                'extract': [
                    {'name': 'chat_id', 'path': '$.data'},
                ],
                'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 200},
                'errorMessagePath': '$.message',
            },
            {
                'key': 'send_message',
                'name': '发送消息',
                'method': 'POST',
                'path': '/application/chat_message/{{chat_id}}',
                'headers': [
                    {'key': 'AUTHORIZATION', 'value': '{{apiKey}}'},
                    {'key': 'Accept', 'value': 'application/json'},
                    {'key': 'Content-Type', 'value': 'application/json'},
                ],
                'body': {'message': '{{message}}', 'stream': False},
                'extract': [
                    {'name': 'chat_id', 'path': '$.data.chat_id'},
                ],
                'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 200},
                'errorMessagePath': '$.message',
            },
        ],
        'answerPaths': ['$.data.content', '$.data.answer_list.0.content'],
    }


def default_scheme_b_config() -> dict:
    common_headers = [
        {'key': 'Authorization', 'value': 'Bearer {{apiKey}}'},
        {'key': 'Accept', 'value': 'application/json'},
        {'key': 'Content-Type', 'value': 'application/json'},
    ]
    return {
        'schemeType': THIRD_PARTY_CHATBOT_SCHEME_B,
        'steps': [
            {
                'key': 'send_message',
                'name': '发送消息',
                'method': 'POST',
                'path': '/apps/{{externalApplicationId}}/chat',
                'headers': copy.deepcopy(common_headers),
                'body': {'query': '{{message}}'},
                'extract': [
                    {'name': 'sessionId', 'path': '$.data.sessionId'},
                ],
                'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 1},
                'errorMessagePath': '$.message',
            },
        ],
        'streaming': {
            'enabled': True,
            'sessionStep': {
                'key': 'create_session',
                'name': '创建会话',
                'method': 'POST',
                'path': '/apps/{{externalApplicationId}}/sessions',
                'headers': copy.deepcopy(common_headers),
                'body': {},
                'extract': [{'name': 'sessionId', 'path': '$.data.sessionId'}],
                'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 1},
                'errorMessagePath': '$.message',
            },
            'messageStep': {
                'key': 'stream_message',
                'name': '流式发送消息',
                'method': 'POST',
                'path': '/apps/{{externalApplicationId}}/sessions/{{sessionId}}/chat',
                'headers': [
                    {'key': 'Authorization', 'value': 'Bearer {{apiKey}}'},
                    {'key': 'Accept', 'value': 'text/event-stream'},
                    {'key': 'Content-Type', 'value': 'application/json'},
                ],
                'body': {
                    'query': '{{message}}',
                    'history': [],
                    'deepThinkingEnabled': False,
                    'deepThinkingLevel': None,
                },
                'success': {'httpStatus': '200-299'},
                'errorMessagePath': '$.content',
            },
            'events': {
                'typePath': '$.type',
                'deltaType': 'delta',
                'doneType': 'done',
                'errorType': 'error',
                'deltaPath': '$.content',
                'errorPath': '$.content',
            },
        },
        'answerPaths': ['$.data.answer'],
    }


def default_config_for_scheme(scheme_type: str | None = None) -> dict:
    if scheme_type == THIRD_PARTY_CHATBOT_SCHEME_B:
        return default_scheme_b_config()
    return default_scheme_a_config()


def is_sensitive_key(key: str) -> bool:
    normalized = str(key or '').strip().lower()
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def mask_secret(value: str) -> str:
    value = str(value or '')
    if not value:
        return ''
    if len(value) <= 8:
        return '*' * len(value)
    return f'{value[:4]}****{value[-4:]}'


def mask_sensitive_config(config: dict) -> dict:
    masked = copy.deepcopy(config or {})
    for step in _iter_config_steps(masked):
        for header in step.get('headers') or []:
            if isinstance(header, dict) and is_sensitive_key(header.get('key')) and not _contains_template_reference(header.get('value')):
                header['value'] = mask_secret(header.get('value'))
        _mask_sensitive_mapping(step.get('body'))
    return masked


def _iter_config_steps(config: dict):
    if not isinstance(config, dict):
        return
    for step in config.get('steps') or []:
        if isinstance(step, dict):
            yield step
    streaming = config.get('streaming')
    if isinstance(streaming, dict):
        for key in ('sessionStep', 'messageStep'):
            step = streaming.get(key)
            if isinstance(step, dict):
                yield step


def _contains_template_reference(value) -> bool:
    return isinstance(value, str) and bool(TEMPLATE_PATTERN.search(value))


def _mask_sensitive_mapping(value):
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if is_sensitive_key(key) and not _contains_template_reference(item):
                value[key] = mask_secret(item)
            else:
                _mask_sensitive_mapping(item)
    elif isinstance(value, list):
        for item in value:
            _mask_sensitive_mapping(item)


def merge_sensitive_config(next_config: dict, current_config: dict | None = None) -> dict:
    current_config = current_config or {}
    merged = copy.deepcopy(next_config or {})
    current_steps = {
        str(step.get('key') or index): step
        for index, step in enumerate(_iter_config_steps(current_config) or [])
        if isinstance(step, dict)
    }
    for index, step in enumerate(_iter_config_steps(merged) or []):
        if not isinstance(step, dict):
            continue
        step_key = str(step.get('key') or index)
        current_step = current_steps.get(step_key) or {}
        current_headers = {
            str(header.get('key') or ''): header.get('value', '')
            for header in current_step.get('headers') or []
            if isinstance(header, dict)
        }
        for header in step.get('headers') or []:
            if not isinstance(header, dict):
                continue
            key = str(header.get('key') or '')
            value = str(header.get('value') or '')
            if is_sensitive_key(key) and _looks_masked(value) and key in current_headers:
                header['value'] = current_headers[key]
        _restore_masked_mapping(step.get('body'), current_step.get('body'))
    return merged


def _looks_masked(value: str) -> bool:
    return bool(value) and '*' in value and len(value.replace('*', '')) <= 8


def _restore_masked_mapping(next_value, current_value):
    if isinstance(next_value, dict) and isinstance(current_value, dict):
        for key, item in list(next_value.items()):
            if is_sensitive_key(key) and isinstance(item, str) and _looks_masked(item) and key in current_value:
                next_value[key] = current_value[key]
            else:
                _restore_masked_mapping(item, current_value.get(key))
    elif isinstance(next_value, list) and isinstance(current_value, list):
        for index, item in enumerate(next_value):
            current_item = current_value[index] if index < len(current_value) else None
            _restore_masked_mapping(item, current_item)


def _build_runtime(provider, message: str, initial_variables: dict | None = None) -> dict:
    runtime = {
        'message': str(message or '').strip(),
        'apiKey': normalize_chatbot_api_key(provider.api_key),
    }
    if not runtime['message']:
        raise RuntimeError('第三方机器人消息不能为空')
    if not runtime['apiKey']:
        raise RuntimeError('第三方机器人应用密钥未配置')
    for key, value in (initial_variables or {}).items():
        key = str(key or '').strip()
        if key and key not in {'message', 'apiKey'} and value not in (None, ''):
            runtime[key] = value
    return runtime


def _session_key(provider, config: dict, runtime: dict) -> str:
    return (
        f'{provider.provider_type}:integration:'
        f'{config.get("schemeType") or THIRD_PARTY_CHATBOT_SCHEME_A}:'
        f'{runtime.get("externalApplicationId") or runtime.get("chatbotId") or ""}'
    )


def _load_external_session(conversation, session_key: str, runtime: dict) -> None:
    if conversation is None:
        return
    session = conversation.external_session or {}
    item = session.get(session_key)
    if isinstance(item, dict):
        for key, value in item.items():
            if value not in (None, ''):
                runtime[key] = value


def _store_external_session(conversation, session_key: str, runtime: dict) -> None:
    if conversation is None:
        return
    stored = {key: value for key, value in runtime.items() if key not in {'message', 'apiKey'} and value not in (None, '')}
    if stored:
        session = dict(conversation.external_session or {})
        session[session_key] = stored
        conversation.external_session = session
        conversation.save(update_fields=['external_session', 'updated_at'])


def run_chatbot_integration_config(
    *,
    provider,
    config: dict,
    message: str,
    conversation=None,
    initial_variables: dict | None = None,
    timeout: int = 120,
) -> dict:
    runtime = _build_runtime(provider, message, initial_variables)
    config = normalize_integration_config(config)
    session_key = _session_key(provider, config, runtime)
    _load_external_session(conversation, session_key, runtime)

    step_results = []
    last_payload = None
    try:
        with httpx.Client(timeout=timeout) as client:
            for step in config.get('steps') or []:
                step_summary = {
                    'key': step.get('key') or '',
                    'name': step.get('name') or '',
                    'statusCode': None,
                    'success': False,
                }
                try:
                    response = _execute_config_step(client, provider.api_base_url, step, runtime)
                    step_summary['statusCode'] = response.status_code
                    payload = _response_json(response)
                    last_payload = payload
                    _assert_step_success(step, response, payload)
                    _extract_step_variables(step, payload, runtime)
                    step_summary['success'] = True
                    step_results.append(step_summary)
                except httpx.TimeoutException as exc:
                    step_summary['message'] = '第三方机器人请求超时'
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError('第三方机器人请求超时', steps=step_results) from exc
                except httpx.HTTPError as exc:
                    step_summary['message'] = '第三方机器人连接失败'
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError('第三方机器人连接失败', steps=step_results) from exc
                except RuntimeError as exc:
                    step_summary['message'] = str(exc)[:200]
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError(str(exc), steps=step_results) from exc
    except httpx.TimeoutException as exc:
        raise ThirdPartyChatbotIntegrationError('第三方机器人请求超时', steps=step_results) from exc
    except httpx.HTTPError as exc:
        raise ThirdPartyChatbotIntegrationError('第三方机器人连接失败', steps=step_results) from exc

    _store_external_session(conversation, session_key, runtime)

    answer = ''
    for path in config.get('answerPaths') or []:
        value = get_json_path(last_payload, path)
        if value not in (None, ''):
            answer = str(value).strip()
            if answer:
                break
    return {'answer': answer, 'steps': step_results, 'variables': runtime}


def supports_streaming(config: dict | None) -> bool:
    normalized = normalize_integration_config(config)
    streaming = normalized.get('streaming')
    return isinstance(streaming, dict) and streaming.get('enabled') is True and isinstance(streaming.get('messageStep'), dict)


async def stream_chatbot_message(
    chatbot: ThirdPartyChatbotApplication,
    message: str,
    *,
    conversation=None,
    timeout: int = 120,
):
    integration = getattr(chatbot, 'integration', None)
    if integration is None:
        raise RuntimeError('第三方机器人未绑定可用方案')
    if not integration.is_active:
        raise RuntimeError('第三方机器人方案未启用')

    provider = chatbot.provider
    config = normalize_integration_config(integration.config or {})
    streaming = config.get('streaming') if isinstance(config.get('streaming'), dict) else {}
    if not supports_streaming(config):
        answer = send_chatbot_message(chatbot, message, conversation=conversation, timeout=timeout)
        if answer:
            yield answer
        return

    runtime = _build_runtime(
        provider,
        message,
        {
            'chatbotId': chatbot.id,
            'externalApplicationId': chatbot.external_application_id,
        },
    )
    session_key = _session_key(provider, config, runtime)
    _load_external_session(conversation, session_key, runtime)

    session_step = streaming.get('sessionStep') if isinstance(streaming.get('sessionStep'), dict) else None
    message_step = streaming.get('messageStep') or {}
    events = streaming.get('events') if isinstance(streaming.get('events'), dict) else {}
    step_results = []

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if session_step and not runtime.get('sessionId'):
                step_summary = _build_step_summary(session_step)
                try:
                    response = await _execute_config_step_async(client, provider.api_base_url, session_step, runtime)
                    step_summary['statusCode'] = response.status_code
                    payload = _response_json(response)
                    _assert_step_success(session_step, response, payload)
                    _extract_step_variables(session_step, payload, runtime)
                    step_summary['success'] = True
                    step_results.append(step_summary)
                except httpx.TimeoutException as exc:
                    step_summary['message'] = '第三方机器人请求超时'
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError('第三方机器人请求超时', steps=step_results) from exc
                except httpx.HTTPError as exc:
                    step_summary['message'] = '第三方机器人连接失败'
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError('第三方机器人连接失败', steps=step_results) from exc
                except RuntimeError as exc:
                    step_summary['message'] = str(exc)[:200]
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError(str(exc), steps=step_results) from exc

            step_summary = _build_step_summary(message_step)
            method = str(message_step.get('method') or 'POST').upper()
            url, kwargs = _build_config_step_request(provider.api_base_url, message_step, runtime)
            async with client.stream(method, url, **kwargs) as response:
                step_summary['statusCode'] = response.status_code
                if not _http_status_matches(response.status_code, str((message_step.get('success') or {}).get('httpStatus') or '200-299')):
                    error_body = (await response.aread()).decode('utf-8', errors='ignore')
                    step_summary['message'] = f'第三方机器人流式请求失败 (HTTP {response.status_code})'
                    step_results.append(step_summary)
                    raise ThirdPartyChatbotIntegrationError(
                        f'第三方机器人流式请求失败 (HTTP {response.status_code}): {error_body[:200]}',
                        steps=step_results,
                    )

                emitted = False
                event_name = None
                async for line in response.aiter_lines():
                    if line and line.startswith('event:'):
                        event_name = line[6:].strip()
                        continue
                    data_str = _parse_sse_data_line(line)
                    if data_str is None:
                        continue
                    data_str = data_str.strip()
                    if not data_str or data_str == '[DONE]':
                        if data_str == '[DONE]':
                            break
                        continue
                    try:
                        payload = json.loads(data_str)
                    except json.JSONDecodeError:
                        payload = {'type': event_name, 'content': data_str} if event_name else None
                    if not isinstance(payload, dict):
                        continue
                    event_type = get_json_path(payload, events.get('typePath') or '$.type')
                    if event_type == (events.get('doneType') or 'done'):
                        break
                    if event_type == (events.get('errorType') or 'error'):
                        message_text = get_json_path(payload, events.get('errorPath') or '$.content') or '第三方机器人流式响应错误'
                        raise RuntimeError(str(message_text)[:200])
                    if event_type and event_type != (events.get('deltaType') or 'delta'):
                        continue
                    text = get_json_path(payload, events.get('deltaPath') or '$.content')
                    if text not in (None, ''):
                        emitted = True
                        yield str(text)

                step_summary['success'] = True
                step_results.append(step_summary)
                await sync_to_async(_store_external_session, thread_sensitive=True)(conversation, session_key, runtime)
                if not emitted:
                    raise ThirdPartyChatbotIntegrationError('第三方机器人没有返回有效回复', steps=step_results)
    except ThirdPartyChatbotIntegrationError:
        raise
    except httpx.TimeoutException as exc:
        raise ThirdPartyChatbotIntegrationError('第三方机器人请求超时', steps=step_results) from exc
    except httpx.HTTPError as exc:
        raise ThirdPartyChatbotIntegrationError('第三方机器人连接失败', steps=step_results) from exc
    except RuntimeError as exc:
        raise ThirdPartyChatbotIntegrationError(str(exc), steps=step_results) from exc


def normalize_integration_config(config: dict | None, *, scheme_type: str | None = None) -> dict:
    normalized_scheme_type = scheme_type
    if isinstance(config, dict):
        normalized_scheme_type = normalized_scheme_type or config.get('schemeType')
    normalized_scheme_type = normalized_scheme_type or THIRD_PARTY_CHATBOT_SCHEME_A
    base = default_config_for_scheme(normalized_scheme_type)
    if not isinstance(config, dict):
        return base
    result = copy.deepcopy(config)
    result['schemeType'] = normalized_scheme_type
    if not result.get('steps'):
        result['steps'] = copy.deepcopy(base['steps'])
    if not result.get('answerPaths'):
        result['answerPaths'] = copy.deepcopy(base['answerPaths'])
    if not result.get('streaming') and base.get('streaming'):
        result['streaming'] = copy.deepcopy(base['streaming'])
    return result


def _build_step_summary(step: dict) -> dict:
    return {
        'key': step.get('key') or '',
        'name': step.get('name') or '',
        'statusCode': None,
        'success': False,
    }


def _build_config_step_request(base_url: str, step: dict, variables: dict) -> tuple[str, dict]:
    url = _build_step_url(base_url, render_template(step.get('path') or '', variables))
    headers = {}
    for header in step.get('headers') or []:
        if not isinstance(header, dict):
            continue
        key = str(header.get('key') or '').strip()
        if key:
            headers[key] = render_template(header.get('value') or '', variables)
    body = render_value(step.get('body'), variables)
    kwargs = {'headers': headers}
    method = str(step.get('method') or 'GET').upper()
    if method not in {'GET', 'HEAD'}:
        kwargs['json'] = body if isinstance(body, (dict, list)) else {}
    return url, kwargs


def _execute_config_step(client: httpx.Client, base_url: str, step: dict, variables: dict) -> httpx.Response:
    method = str(step.get('method') or 'GET').upper()
    url, kwargs = _build_config_step_request(base_url, step, variables)
    return client.request(method, url, **kwargs)


async def _execute_config_step_async(client: httpx.AsyncClient, base_url: str, step: dict, variables: dict) -> httpx.Response:
    method = str(step.get('method') or 'GET').upper()
    url, kwargs = _build_config_step_request(base_url, step, variables)
    return await client.request(method, url, **kwargs)


def _build_step_url(base_url: str, path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return urljoin(f'{str(base_url or "").rstrip("/")}/', str(path or '').lstrip('/'))


def render_value(value, variables: dict):
    if isinstance(value, str):
        return render_template(value, variables)
    if isinstance(value, list):
        return [render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, variables) for key, item in value.items()}
    return value


def render_template(value: str, variables: dict) -> str:
    text = str(value or '')
    def replace(match):
        key = match.group(1)
        replacement = variables.get(key, '')
        return str(replacement if replacement is not None else '')
    return TEMPLATE_PATTERN.sub(replace, text)


def _parse_sse_data_line(line: str) -> str | None:
    if not line or not line.startswith('data:'):
        return None
    return line[5:].lstrip()


def _response_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError('第三方机器人响应不是有效 JSON') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('第三方机器人响应格式错误')
    return payload


def _assert_step_success(step: dict, response: httpx.Response, payload: dict) -> None:
    success = step.get('success') if isinstance(step.get('success'), dict) else {}
    if not _http_status_matches(response.status_code, str(success.get('httpStatus') or '200-299')):
        raise RuntimeError(f"{step.get('name') or '第三方请求'}失败 (HTTP {response.status_code})")
    body_path = success.get('bodyPath')
    if body_path:
        actual = get_json_path(payload, body_path)
        expected = success.get('equals')
        if actual != expected and str(actual) != str(expected):
            message = get_json_path(payload, step.get('errorMessagePath') or '$.message') or '第三方机器人请求失败'
            raise RuntimeError(str(message)[:200])


def _http_status_matches(status_code: int, rule: str) -> bool:
    for part in str(rule or '').split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            try:
                if int(start) <= status_code <= int(end):
                    return True
            except ValueError:
                continue
        else:
            try:
                if status_code == int(part):
                    return True
            except ValueError:
                continue
    return False


def _extract_step_variables(step: dict, payload: dict, variables: dict) -> None:
    for item in step.get('extract') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        path = str(item.get('path') or '').strip()
        if not name or not path:
            continue
        value = get_json_path(payload, path)
        if value not in (None, ''):
            variables[name] = value


def get_json_path(payload, path: str):
    if not path or path == '$':
        return payload
    if not path.startswith('$.'):
        return None
    current = payload
    for part in path[2:].split('.'):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current
