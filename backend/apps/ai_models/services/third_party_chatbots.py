from __future__ import annotations

import httpx

from apps.ai_models.models import (
    THIRD_PARTY_PROVIDER_IHUAPENG,
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
    if chatbot.provider.provider_type == THIRD_PARTY_PROVIDER_IHUAPENG:
        return _send_ihuapeng_message(chatbot, message, conversation=conversation, timeout=timeout)
    raise RuntimeError('暂不支持的第三方机器人类型')


def normalize_chatbot_api_key(value: str) -> str:
    return str(value or '').strip().strip('`').strip()


def _session_key(chatbot: ThirdPartyChatbotApplication) -> str:
    return f'{chatbot.provider.provider_type}:{chatbot.id}'


def _get_conversation_chat_id(conversation, chatbot: ThirdPartyChatbotApplication) -> str:
    if conversation is None:
        return ''
    session = conversation.external_session or {}
    item = session.get(_session_key(chatbot))
    if isinstance(item, dict) and item.get('chat_id'):
        return str(item['chat_id'])
    return ''


def _save_conversation_chat_id(conversation, chatbot: ThirdPartyChatbotApplication, chat_id: str) -> None:
    if conversation is None or not chat_id:
        return
    session = dict(conversation.external_session or {})
    session[_session_key(chatbot)] = {
        'chat_id': chat_id,
        'chatbot_id': chatbot.id,
        'provider_type': chatbot.provider.provider_type,
    }
    conversation.external_session = session
    conversation.save(update_fields=['external_session', 'updated_at'])


def _request_json(response: httpx.Response) -> dict:
    if response.status_code != 200:
        raise RuntimeError(f'第三方机器人请求失败 (HTTP {response.status_code})')
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError('第三方机器人响应不是有效 JSON') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('第三方机器人响应格式错误')
    code = payload.get('code')
    if code not in (200, '200'):
        message = str(payload.get('message') or '第三方机器人请求失败').strip()
        raise RuntimeError(message[:200])
    return payload


def _extract_ihuapeng_answer(payload: dict) -> tuple[str, str]:
    data = payload.get('data')
    if not isinstance(data, dict):
        return '', ''
    answer = str(data.get('content') or '').strip()
    if not answer:
        answer_list = data.get('answer_list')
        if isinstance(answer_list, list) and answer_list:
            first_answer = answer_list[0] if isinstance(answer_list[0], dict) else {}
            answer = str(first_answer.get('content') or '').strip()
    chat_id = str(data.get('chat_id') or '').strip()
    return answer, chat_id


def _open_ihuapeng_chat(
    client: httpx.Client,
    chatbot: ThirdPartyChatbotApplication,
    headers: dict[str, str],
) -> str:
    base_url = chatbot.provider.api_base_url.rstrip('/')
    response = client.get(
        f'{base_url}/application/{chatbot.external_application_id}/chat/open',
        headers={'AUTHORIZATION': headers['AUTHORIZATION'], 'Accept': 'application/json'},
    )
    payload = _request_json(response)
    chat_id = str(payload.get('data') or '').strip()
    if not chat_id:
        raise RuntimeError('第三方机器人未返回会话 ID')
    return chat_id


def _send_ihuapeng_message(
    chatbot: ThirdPartyChatbotApplication,
    message: str,
    *,
    conversation=None,
    timeout: int,
) -> str:
    text = str(message or '').strip()
    if not text:
        raise RuntimeError('第三方机器人消息不能为空')

    api_key = normalize_chatbot_api_key(chatbot.provider.api_key)
    if not api_key:
        raise RuntimeError('第三方机器人应用密钥未配置')
    headers = {
        'AUTHORIZATION': api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    base_url = chatbot.provider.api_base_url.rstrip('/')
    chat_id = _get_conversation_chat_id(conversation, chatbot)
    try:
        with httpx.Client(timeout=timeout) as client:
            if not chat_id:
                chat_id = _open_ihuapeng_chat(client, chatbot, headers)
                _save_conversation_chat_id(conversation, chatbot, chat_id)
            response = client.post(
                f'{base_url}/application/chat_message/{chat_id}',
                headers=headers,
                json={
                    'message': text,
                    'stream': False,
                },
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError('第三方机器人请求超时') from exc
    except httpx.HTTPError as exc:
        raise RuntimeError('第三方机器人连接失败') from exc

    payload = _request_json(response)
    answer, response_chat_id = _extract_ihuapeng_answer(payload)
    if response_chat_id and response_chat_id != chat_id:
        _save_conversation_chat_id(conversation, chatbot, response_chat_id)
    if not answer:
        raise RuntimeError('第三方机器人没有返回有效回复')
    return answer
