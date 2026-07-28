from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RealtimeErrorDefinition:
    key: str
    code: str
    default_message: str
    category: str
    description: str
    recommended_action: str
    transports: tuple[str, ...] = ('websocket',)
    legacy_status_code: int | None = None


_ERROR_DEFINITIONS = (
    RealtimeErrorDefinition('DEVICE_CODE_REQUIRED', '1001', '设备码不能为空', '设备运行时', '运行时请求未提供设备码。', '提供已登记的设备码。', ('http', 'websocket'), 44001),
    RealtimeErrorDefinition('DEVICE_NOT_REGISTERED', '1002', '设备未登记', '设备运行时', '设备码未对应任何已登记设备。', '确认设备已在后台登记并使用正确设备码。', ('http', 'websocket'), 44004),
    RealtimeErrorDefinition('DEVICE_CODE_DUPLICATED', '1003', '设备码存在重复绑定，请联系后台处理', '设备运行时', '同一设备码对应多条设备记录，无法安全确定设备。', '由平台管理员清理重复的设备码绑定。', ('http', 'websocket'), 44009),
    RealtimeErrorDefinition('DEVICE_TENANT_UNBOUND', '1004', '设备未绑定公司', '设备运行时', '运行时操作要求设备归属公司，但设备尚未绑定公司。', '在后台为设备绑定有效公司。', ('http', 'websocket'), 44011),
    RealtimeErrorDefinition('DEVICE_TENANT_DISABLED', '1005', '公司已停用', '设备运行时', '设备所属公司已停用。', '恢复公司状态或为设备绑定可用公司。', ('http', 'websocket'), 44012),
    RealtimeErrorDefinition('DEVICE_DISABLED', '1006', '设备已停用', '设备运行时', '设备已被后台停用。', '在后台启用设备后重试。', ('http', 'websocket'), 44013),
    RealtimeErrorDefinition('DEVICE_EXPIRED', '1007', '设备授权已过期', '设备运行时', '设备授权有效期已经结束。', '续期设备授权后重试。', ('http', 'websocket'), 44014),
    RealtimeErrorDefinition('DEVICE_AGENT_UNBOUND', '1008', '设备未绑定可用智能体', '设备运行时', '设备没有可用且已启用的智能体绑定。', '为设备绑定并启用智能体。', ('http', 'websocket'), 44021),
    RealtimeErrorDefinition('DEVICE_APPLICATION_INACTIVE', '1009', '设备绑定应用未启用', '设备运行时', '设备绑定的应用当前处于未启用状态。', '在后台启用设备绑定应用。', ('http', 'websocket'), 44022),
    RealtimeErrorDefinition('REALTIME_RUNTIME_CONFIG_SUBSCRIPTION_FAILED', '1010', '设备运行时配置订阅失败', '实时协议', '无法建立设备运行时配置订阅。', '稍后重试；持续失败时检查服务端日志。'),
    RealtimeErrorDefinition('REALTIME_MESSAGE_REQUIRED', '1011', '实时命令必须是 JSON 文本消息', '实时协议', 'WebSocket 收到不含文本的命令帧。', '使用 JSON 文本帧发送实时命令。'),
    RealtimeErrorDefinition('REALTIME_INVALID_JSON', '1012', '实时命令必须是有效 JSON', '实时协议', 'WebSocket 收到无法解析的命令文本。', '检查客户端 JSON 编码。'),
    RealtimeErrorDefinition('REALTIME_COMMAND_TYPE_REQUIRED', '1013', '实时命令类型不能为空', '实时协议', '命令未提供有效 type 字段。', '提供受支持的实时命令 type。'),
    RealtimeErrorDefinition('REALTIME_UNKNOWN_COMMAND', '1014', '不支持的实时命令', '实时协议', '客户端请求的实时命令不受支持。', '升级客户端或使用已发布的命令类型。'),
    RealtimeErrorDefinition('REALTIME_UNAUTHORIZED', '1015', '实时会话未授权', '实时协议', '当前凭据不能建立所请求的实时会话。', '检查访问令牌和权限。'),
    RealtimeErrorDefinition('REALTIME_DEVICE_NOT_AVAILABLE', '1016', '设备不可用', '实时协议', '设备不存在或当前不能用于实时操作。', '确认设备已登记、启用且具备所需绑定。'),
    RealtimeErrorDefinition('REALTIME_DEVICE_STATUS_NOT_STARTED', '1017', '设备状态会话尚未启动', '实时协议', '在启动设备状态会话前请求了心跳。', '先发送 device.status.start。'),
    RealtimeErrorDefinition('REALTIME_VOICE_NOT_AVAILABLE', '1018', '音色不可用', '实时协议', '请求的音色不存在或不可用。', '选择已启用且可见的音色。'),
    RealtimeErrorDefinition('ASR_UNAUTHORIZED', '1019', 'ASR 会话未授权', '语音识别', '当前凭据不能建立 ASR 会话。', '检查访问令牌、设备码和 ASR 权限。'),
    RealtimeErrorDefinition('ASR_NOT_READY', '1020', 'ASR 服务未就绪', '语音识别', 'ASR 配置未启用或缺少必要配置。', '由平台管理员完成并启用 ASR 配置。'),
    RealtimeErrorDefinition('ASR_SESSION_NOT_STARTED', '1021', 'ASR 会话尚未启动', '语音识别', '对不存在的 ASR 会话执行了操作。', '先发送 asr.session.start。'),
    RealtimeErrorDefinition('ASR_UPSTREAM_ERROR', '1022', 'ASR 上游服务暂不可用', '语音识别', '连接或调用 ASR 上游服务失败。', '稍后重试；持续失败时检查服务端日志和上游配置。'),
    RealtimeErrorDefinition('TTS_UNAUTHORIZED', '1023', 'TTS 会话未授权', '语音合成', '当前凭据不能建立 TTS 会话。', '检查访问令牌、设备码和 TTS 权限。'),
    RealtimeErrorDefinition('TTS_NOT_READY', '1024', 'TTS 服务未就绪', '语音合成', 'TTS 配置未启用或缺少必要配置。', '由平台管理员完成并启用 TTS 配置。'),
    RealtimeErrorDefinition('TTS_VOICE_NOT_AVAILABLE', '1025', 'TTS 音色不可用', '语音合成', '请求的音色未配置或不支持当前模型。', '选择已配置且受当前模型支持的音色。'),
    RealtimeErrorDefinition('TTS_SESSION_NOT_STARTED', '1026', 'TTS 会话尚未启动', '语音合成', '对不存在的 TTS 会话执行了操作。', '先发送 tts.session.start。'),
    RealtimeErrorDefinition('TTS_UPSTREAM_ERROR', '1027', 'TTS 上游服务暂不可用', '语音合成', '调用 TTS 上游服务失败。', '稍后重试；持续失败时检查服务端日志和上游配置。'),
    RealtimeErrorDefinition('LLM_DEVICE_CODE_REQUIRED', '1028', '设备码不能为空', '大语言模型', 'LLM 实时请求未提供设备码。', '提供已登记的设备码。'),
    RealtimeErrorDefinition('LLM_QUESTION_REQUIRED', '1029', '问题内容不能为空', '大语言模型', 'LLM 实时请求未提供问题内容。', '提供非空的问题文本。'),
    RealtimeErrorDefinition('LLM_SESSION_NOT_STARTED', '1030', 'LLM 会话尚未启动', '大语言模型', '对不存在的 LLM 会话执行了操作。', '先发送 llm.session.start。'),
    RealtimeErrorDefinition('LLM_UPSTREAM_ERROR', '1031', 'LLM 上游服务暂不可用', '大语言模型', '调用 LLM 或第三方机器人服务失败。', '稍后重试；持续失败时检查服务端日志和上游配置。'),
    RealtimeErrorDefinition('LLM_EMPTY_RESPONSE', '1032', 'LLM 未返回有效回复', '大语言模型', 'LLM 没有返回可供设备展示的内容。', '稍后重试；持续失败时检查模型配置。'),
    RealtimeErrorDefinition('AGENT_SESSION_NOT_STARTED', '1033', '智能体会话尚未启动', '智能体', '对不存在的智能体会话执行了操作。', '先发送 agent.session.start。'),
    RealtimeErrorDefinition('AGENT_ASR_SESSION_NOT_STARTED', '1034', '智能体 ASR 会话尚未启动', '智能体', '语音智能体会话尚未建立 ASR 上游会话。', '先启动语音智能体会话，或提供文本问题。'),
    RealtimeErrorDefinition('INTERNAL_ERROR', '1035', '服务内部错误，请稍后重试', '内部错误', '发生未分类的服务端错误。', '稍后重试；持续失败时提供关联 ID 给平台管理员。'),
)

ERROR_DEFINITIONS: tuple[RealtimeErrorDefinition, ...] = _ERROR_DEFINITIONS
ERROR_DEFINITIONS_BY_CODE: Mapping[str, RealtimeErrorDefinition] = MappingProxyType(
    {definition.code: definition for definition in ERROR_DEFINITIONS}
)
_ERROR_DEFINITIONS_BY_KEY: Mapping[str, RealtimeErrorDefinition] = MappingProxyType(
    {definition.key: definition for definition in ERROR_DEFINITIONS}
)


def get_error_definition(code: str) -> RealtimeErrorDefinition | None:
    return ERROR_DEFINITIONS_BY_CODE.get(str(code or '').strip())


def get_error_definition_by_key(key: str) -> RealtimeErrorDefinition | None:
    return _ERROR_DEFINITIONS_BY_KEY.get(str(key or '').strip().upper())


def require_error_definition_by_key(key: str) -> RealtimeErrorDefinition:
    definition = get_error_definition_by_key(key)
    if definition is None:
        raise ValueError(f'Unknown realtime error key: {key}')
    return definition


def internal_error_definition() -> RealtimeErrorDefinition:
    return require_error_definition_by_key('INTERNAL_ERROR')
