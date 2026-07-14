from apps.devices.models import Device, DeviceChatLog


def record_device_chat_log(
    device: Device,
    question_text: str,
    answer_text: str,
    *,
    source: str,
    request_id: str = '',
    trace_id: str = '',
    model_name: str = '',
    conversation_id: int | None = None,
    runtime_session_id: str = '',
    answer_blocks: list[dict] | None = None,
    command_dispatch_diagnostics: dict | None = None,
) -> DeviceChatLog | None:
    question = str(question_text or '').strip()
    answer = str(answer_text or '').strip()
    if not question or not answer:
        return None

    return DeviceChatLog.objects.create(
        tenant=device.tenant,
        application=device.application,
        agent_application=device.effective_agent_application,
        device=device,
        conversation_id=conversation_id,
        runtime_session_id=str(runtime_session_id or ''),
        code=device.code,
        source=source,
        question_text=question,
        answer_text=answer,
        answer_blocks=answer_blocks or [{'type': 'text', 'text': answer}],
        command_dispatch_diagnostics=command_dispatch_diagnostics or {},
        request_id=str(request_id or ''),
        trace_id=str(trace_id or ''),
        model_name=str(model_name or ''),
    )
