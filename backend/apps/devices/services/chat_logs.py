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
        code=device.code,
        source=source,
        question_text=question,
        answer_text=answer,
        request_id=str(request_id or ''),
        trace_id=str(trace_id or ''),
        model_name=str(model_name or ''),
    )
