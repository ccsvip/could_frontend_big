from __future__ import annotations

from django.db.models import BigIntegerField, Case, CharField, Count, F, Max, Min, Q, QuerySet, Value, When

from apps.ai_models.services.reply_blocks import serialize_reply_blocks, text_to_blocks
from apps.ai_models.services.agent_knowledge import serialize_knowledge_references
from apps.devices.models import DeviceChatLog


def _device_chat_session_display(log: DeviceChatLog) -> dict:
    conversation = log.conversation
    return {
        'title': f'{log.device.name if log.device else log.code or "设备"} 设备运行时',
        'runtimeBackendType': conversation.runtime_backend_type if conversation else 'platform_llm',
        'llmModelName': log.model_name,
        'llmModelDisplayName': log.model_name,
        'llmProviderName': (
            conversation.llm_model.provider.name
            if conversation and conversation.llm_model and conversation.llm_model.provider
            else None
        ),
        'thirdPartyChatbotName': (
            conversation.third_party_chatbot.name
            if conversation and conversation.third_party_chatbot
            else ''
        ),
        'thirdPartyChatbotProviderName': (
            conversation.third_party_chatbot.provider.name
            if conversation and conversation.third_party_chatbot and conversation.third_party_chatbot.provider
            else None
        ),
    }


def device_chat_session_groups(queryset: QuerySet[DeviceChatLog]) -> QuerySet:
    runtime_device_code = Case(
        When(
            ~Q(runtime_session_id=''),
            then=F('code'),
        ),
        default=Value(''),
        output_field=CharField(),
    )
    grouped_conversation_id = Case(
        When(runtime_session_id='', then=F('conversation_id')),
        default=Value(None),
        output_field=BigIntegerField(),
    )
    legacy_log_id = Case(
        When(runtime_session_id='', conversation_id__isnull=True, then=F('id')),
        default=Value(None),
        output_field=BigIntegerField(),
    )
    return (
        queryset
        .annotate(
            runtime_device_code=runtime_device_code,
            grouped_conversation_id=grouped_conversation_id,
            legacy_log_id=legacy_log_id,
        )
        .values('runtime_device_code', 'runtime_session_id', 'grouped_conversation_id', 'legacy_log_id')
        .annotate(
            seed_log_id=Min('id'),
            latest_log_id=Max('id'),
            interaction_count=Count('id'),
            first_activity_at=Min('created_at'),
            latest_activity_at=Max('created_at'),
        )
        .order_by('-latest_activity_at', '-seed_log_id')
    )


def serialize_device_chat_session_groups(groups: list[dict], queryset: QuerySet[DeviceChatLog]) -> list[dict]:
    latest_log_ids = [group['latest_log_id'] for group in groups]
    latest_logs = {
        log.id: log
        for log in queryset.filter(id__in=latest_log_ids).select_related(
            'device',
            'conversation__llm_model__provider',
            'conversation__third_party_chatbot__provider',
        )
    }
    results = []
    for group in groups:
        log = latest_logs[group['latest_log_id']]
        results.append({
            'id': group['seed_log_id'],
            'deviceCode': log.code,
            'deviceName': log.device.name if log.device else '',
            'conversationId': log.conversation_id,
            'runtimeSessionId': log.runtime_session_id,
            'summary': log.question_text,
            'lastMessage': log.answer_text,
            'messageCount': group['interaction_count'] * 2,
            **_device_chat_session_display(log),
            'createdAt': group['first_activity_at'],
            'updatedAt': group['latest_activity_at'],
        })
    return results


def device_chat_session_logs(queryset: QuerySet[DeviceChatLog], seed: DeviceChatLog) -> QuerySet[DeviceChatLog]:
    if seed.runtime_session_id:
        return queryset.filter(
            agent_application_id=seed.agent_application_id,
            code=seed.code,
            runtime_session_id=seed.runtime_session_id,
        )
    if seed.conversation_id is not None:
        return queryset.filter(conversation_id=seed.conversation_id, runtime_session_id='')
    return queryset.filter(id=seed.id)


def serialize_device_chat_session(logs: list[DeviceChatLog], *, request=None) -> dict:
    ordered_logs = sorted(logs, key=lambda log: (log.created_at, log.id))
    first_log = ordered_logs[0]
    last_log = ordered_logs[-1]
    conversation = last_log.conversation
    messages = []
    for log in ordered_logs:
        messages.extend([
            {
                'id': log.id * 2,
                'conversationId': -first_log.id,
                'role': 'user',
                'content': log.question_text,
                'contentBlocks': text_to_blocks(log.question_text),
                'feedback': 'none',
                'createdAt': log.created_at,
            },
            {
                'id': log.id * 2 + 1,
                'conversationId': -first_log.id,
                'role': 'assistant',
                'content': log.answer_text,
                'contentBlocks': serialize_reply_blocks(
                    log.answer_blocks or text_to_blocks(log.answer_text),
                    tenant=log.tenant,
                    request=request,
                ),
                'knowledgeReferences': serialize_knowledge_references(log.knowledge_references),
                'commandDispatch': log.command_dispatch_diagnostics,
                'feedback': 'none',
                'createdAt': log.created_at,
            },
        ])
    return {
        'id': first_log.id,
        'deviceCode': first_log.code,
        'deviceName': first_log.device.name if first_log.device else '',
        'applicationId': first_log.agent_application_id,
        'conversationId': first_log.conversation_id,
        'runtimeSessionId': first_log.runtime_session_id,
        'summary': first_log.question_text,
        'lastMessage': last_log.answer_text,
        'messageCount': len(messages),
        **_device_chat_session_display(last_log),
        'llmModelId': conversation.llm_model_id if conversation else None,
        'thirdPartyChatbotId': conversation.third_party_chatbot_id if conversation else None,
        'systemPrompt': conversation.system_prompt if conversation else '',
        'temperature': conversation.temperature if conversation else 0,
        'maxTokens': conversation.max_tokens if conversation else 0,
        'maxTokensUnlimited': conversation.max_tokens_unlimited if conversation else False,
        'messages': messages,
        'createdAt': first_log.created_at,
        'updatedAt': last_log.created_at,
    }
