import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings


class AliyunCommandServiceError(Exception):
    status_code = 502


class AliyunCommandConfigError(AliyunCommandServiceError):
    status_code = 500


class AliyunCommandUpstreamError(AliyunCommandServiceError):
    status_code = 502


@dataclass(frozen=True)
class AliyunCommandConfig:
    app_id: str
    domain_code: str
    workspace_id: str
    access_key_id: str
    access_key_secret: str
    region: str
    endpoint: str
    api_version: str
    action: str
    timeout_seconds: float


def fetch_aliyun_commands() -> list[dict[str, Any]]:
    config = get_aliyun_command_config()
    payload: dict[str, Any] = {
        'AppId': config.app_id,
        'DomainCode': config.domain_code,
        'PageNumber': 1,
        'PageSize': 100,
    }
    if config.workspace_id:
        payload['WorkspaceId'] = config.workspace_id

    request_body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    headers = build_acs3_headers(config, request_body)

    try:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(
                config.endpoint,
                content=request_body.encode('utf-8'),
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise AliyunCommandUpstreamError('阿里云指令服务请求超时') from exc
    except httpx.RequestError as exc:
        raise AliyunCommandUpstreamError('阿里云指令服务请求失败') from exc

    if response.status_code >= 400:
        raise AliyunCommandUpstreamError(build_upstream_error_message(response))

    try:
        payload = response.json()
    except ValueError as exc:
        raise AliyunCommandUpstreamError('阿里云指令返回数据格式异常') from exc

    return normalize_aliyun_command_items(payload, config.domain_code)


def get_aliyun_command_config() -> AliyunCommandConfig:
    config = AliyunCommandConfig(
        app_id=getattr(settings, 'ALIYUN_MM_APP_ID', '').strip(),
        domain_code=getattr(settings, 'ALIYUN_MM_DOMAIN_CODE', '').strip(),
        workspace_id=getattr(settings, 'MULTIMODAL_WORKSPACE_ID', '').strip(),
        access_key_id=getattr(settings, 'ALIYUN_MM_ACCESS_KEY_ID', '').strip(),
        access_key_secret=getattr(settings, 'ALIYUN_MM_ACCESS_KEY_SECRET', '').strip(),
        region=getattr(settings, 'ALIYUN_MM_REGION', 'cn-beijing').strip() or 'cn-beijing',
        endpoint=getattr(settings, 'ALIYUN_MM_ENDPOINT', '').strip(),
        api_version=getattr(settings, 'ALIYUN_MM_API_VERSION', '2025-09-09').strip() or '2025-09-09',
        action=getattr(settings, 'ALIYUN_MM_LIST_TOOLS_ACTION', 'ListCommand').strip() or 'ListCommand',
        timeout_seconds=float(getattr(settings, 'ALIYUN_MM_TIMEOUT_SECONDS', 15)),
    )
    missing_fields = [
        name
        for name, value in (
            ('ALIYUN_MM_APP_ID', config.app_id),
            ('ALIYUN_MM_DOMAIN_CODE', config.domain_code),
            ('ALIYUN_MM_ACCESS_KEY_ID', config.access_key_id),
            ('ALIYUN_MM_ACCESS_KEY_SECRET', config.access_key_secret),
        )
        if not value
    ]
    if missing_fields:
        raise AliyunCommandConfigError(
            f"阿里云指令配置缺失，请检查：{', '.join(missing_fields)}"
        )

    endpoint = config.endpoint or f'https://sfmmultimodalapp.{config.region}.aliyuncs.com'
    if not endpoint.startswith(('http://', 'https://')):
        endpoint = f'https://{endpoint}'

    return AliyunCommandConfig(
        app_id=config.app_id,
        domain_code=config.domain_code,
        workspace_id=config.workspace_id,
        access_key_id=config.access_key_id,
        access_key_secret=config.access_key_secret,
        region=config.region,
        endpoint=endpoint,
        api_version=config.api_version,
        action=config.action,
        timeout_seconds=config.timeout_seconds,
    )


def build_acs3_headers(config: AliyunCommandConfig, request_body: str) -> dict[str, str]:
    parsed_endpoint = urlparse(config.endpoint)
    canonical_uri = parsed_endpoint.path or '/'
    payload_hash = hashlib.sha256(request_body.encode('utf-8')).hexdigest()
    signed_headers_map = {
        'content-type': 'application/json; charset=utf-8',
        'host': parsed_endpoint.netloc,
        'x-acs-action': config.action,
        'x-acs-content-sha256': payload_hash,
        'x-acs-date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'x-acs-region-id': config.region,
        'x-acs-signature-nonce': str(uuid.uuid4()),
        'x-acs-version': config.api_version,
    }
    signed_header_names = ';'.join(sorted(signed_headers_map))
    canonical_headers = ''.join(
        f'{header_name}:{signed_headers_map[header_name]}\n'
        for header_name in sorted(signed_headers_map)
    )
    canonical_request = (
        f'POST\n{canonical_uri}\n\n{canonical_headers}\n{signed_header_names}\n{payload_hash}'
    )
    string_to_sign = 'ACS3-HMAC-SHA256\n' + hashlib.sha256(
        canonical_request.encode('utf-8')
    ).hexdigest()
    signature = hmac.new(
        config.access_key_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    return {
        'Authorization': (
            'ACS3-HMAC-SHA256 '
            f'Credential={config.access_key_id},'
            f'SignedHeaders={signed_header_names},'
            f'Signature={signature}'
        ),
        'Content-Type': signed_headers_map['content-type'],
        'Host': signed_headers_map['host'],
        'X-Acs-Action': signed_headers_map['x-acs-action'],
        'X-Acs-Content-Sha256': signed_headers_map['x-acs-content-sha256'],
        'X-Acs-Date': signed_headers_map['x-acs-date'],
        'X-Acs-Region-Id': signed_headers_map['x-acs-region-id'],
        'X-Acs-Signature-Nonce': signed_headers_map['x-acs-signature-nonce'],
        'X-Acs-Version': signed_headers_map['x-acs-version'],
    }


def normalize_aliyun_command_items(payload: Any, default_domain_code: str) -> list[dict[str, Any]]:
    raw_items = extract_aliyun_command_items(payload)
    normalized_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise AliyunCommandUpstreamError('阿里云指令返回数据格式异常')
        normalized_item = {
            'domainCode': first_present(item, 'DomainCode', 'domainCode') or default_domain_code,
            'domainName': first_present(item, 'DomainName', 'domainName') or '',
            'toolId': first_present(item, 'ToolId', 'toolId', 'Id', 'id') or '',
            'toolName': first_present(item, 'ToolName', 'toolName', 'Name', 'name') or '',
            'description': (
                first_present(item, 'Description', 'description', 'ToolDescription', 'toolDescription')
                or ''
            ),
            'toolExamples': ensure_list(first_present(item, 'ToolExamples', 'toolExamples')),
            'toolParams': ensure_list(first_present(item, 'ToolParams', 'toolParams')),
        }
        if not normalized_item['toolId'] or not normalized_item['toolName']:
            raise AliyunCommandUpstreamError('阿里云指令返回数据格式异常')
        normalized_items.append(normalized_item)
    return normalized_items


def extract_aliyun_command_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise AliyunCommandUpstreamError('阿里云指令返回数据格式异常')

    candidate_containers = [
        payload,
        payload.get('Data'),
        payload.get('data'),
        payload.get('Result'),
        payload.get('result'),
    ]
    for candidate in candidate_containers:
        if isinstance(candidate, list):
            return candidate
        if not isinstance(candidate, dict):
            continue
        for key in (
            'Items',
            'items',
            'Tools',
            'tools',
            'ToolList',
            'toolList',
            'ToolInfoList',
            'toolInfoList',
        ):
            value = candidate.get(key)
            if isinstance(value, list):
                return value
    raise AliyunCommandUpstreamError('阿里云指令返回数据格式异常')


def build_upstream_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return '阿里云指令服务返回错误'

    if not isinstance(payload, dict):
        return '阿里云指令服务返回错误'

    code = str(first_present(payload, 'Code', 'code') or '').strip()
    message = str(first_present(payload, 'Message', 'message') or '').strip()

    if code == 'SignatureDoesNotMatch':
        return (
            '阿里云签名校验失败，请检查 '
            'ALIYUN_MM_ACCESS_KEY_ID / ALIYUN_MM_ACCESS_KEY_SECRET '
            '是否是同一对有效凭证（SignatureDoesNotMatch）'
        )

    if code:
        concise_message = message.splitlines()[0].strip() if message else ''
        if concise_message:
            return f'阿里云指令服务返回错误（{code}）：{concise_message}'
        return f'阿里云指令服务返回错误（{code}）'

    return '阿里云指令服务返回错误'


def first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return value
    return None


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
