import json
from typing import Any, cast
from urllib.parse import quote, urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.test import Client

from apps.resources.point_runtime import build_point_runtime_lookup_response  # pyright: ignore[reportImplicitRelativeImport]

from .api_catalog import list_api_endpoints
from .models import ApiTester, PointApiTest


@admin.register(PointApiTest)
class PointApiTestAdmin(admin.ModelAdmin):
    change_list_template = 'admin/admin_examples/point_api_test.html'

    def has_module_permission(self, request):
        return self._has_admin_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_admin_access(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        if not self.has_view_permission(request):
            return {}
        return {'view': True}

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied

        command = ''
        endpoint = ''
        http_status = None
        result_json = ''
        form_error = ''

        if request.method == 'POST':
            command = request.POST.get('command', '').strip()
            if command:
                body, http_status = build_point_runtime_lookup_response(request, command)
                result_json = json.dumps(body, ensure_ascii=False, indent=2)
                endpoint = self._build_endpoint_url(command)
            else:
                form_error = '请输入点位命令'

        context = {
            **self.admin_site.each_context(request),
            'title': '指令任务接口测试',
            'opts': self.model._meta,
            'media': self.media,
            'command': command,
            'endpoint': endpoint,
            'http_status': http_status,
            'result_json': result_json,
            'form_error': form_error,
            'curl_command': self._build_curl(endpoint) if endpoint else '',
        }
        if extra_context:
            context.update(extra_context)
        return TemplateResponse(request, self.change_list_template, context)

    def _has_admin_access(self, request) -> bool:
        user = request.user
        return bool(user and user.is_active and user.is_staff)

    def _build_endpoint_url(self, command: str) -> str:
        return f'/api/v1/commands/data/?command={quote(command, safe="")}'

    def _build_curl(self, path: str) -> str:
        return f"curl -X GET '{path}' \\\n  -H 'Accept: application/json'"


@admin.register(ApiTester)
class ApiTesterAdmin(admin.ModelAdmin):
    """通用 API 接口测试 admin 页面：自动列出全部 /api/v1/* 接口，可任选一个测试。"""

    change_list_template = 'admin/admin_examples/api_tester.html'

    def has_module_permission(self, request):
        return self._has_admin_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_admin_access(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        if not self.has_view_permission(request):
            return {}
        return {'view': True}

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied

        endpoints = list_api_endpoints()

        method = (request.POST.get('method') or 'GET').upper()
        path = (request.POST.get('path') or '').strip()
        query = (request.POST.get('query') or '').strip()
        headers_raw = (request.POST.get('headers') or '').strip()
        body_raw = (request.POST.get('body') or '').strip()
        body_format = (request.POST.get('body_format') or 'json').strip().lower()

        endpoint_url = ''
        http_status: int | None = None
        result_text = ''
        result_kind = 'json'  # 'json' | 'text' | 'html' | 'binary'
        form_error = ''
        elapsed_ms: int | None = None
        response_headers: list[tuple[str, str]] = []
        curl_command = ''

        if request.method == 'POST':
            try:
                target_path, body_payload, content_type, header_dict = self._build_call(
                    method=method,
                    path=path,
                    query=query,
                    headers_raw=headers_raw,
                    body_raw=body_raw,
                    body_format=body_format,
                )
            except _FormError as exc:
                form_error = str(exc)
                target_path = ''
                body_payload = b''
                content_type = ''
                header_dict = {}

            if not form_error:
                endpoint_url = target_path
                curl_command = self._build_curl(method, target_path, header_dict, body_raw, body_format)
                http_status, result_text, result_kind, elapsed_ms, response_headers = self._call_api(
                    request=request,
                    method=method,
                    target_path=target_path,
                    body_payload=body_payload,
                    content_type=content_type,
                    header_dict=header_dict,
                )

        # 仅暴露数据中实际出现过的 method（避免 OPTIONS/HEAD 占位 pill 永远计数为 0）。
        present_methods_in_data = sorted({ep['method'] for ep in endpoints})
        canonical_order = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
        method_pills = [m for m in canonical_order if m in present_methods_in_data]
        # 表单的 method <select> 仍提供全量，便于手工测试任意 method。

        context = {
            **self.admin_site.each_context(request),
            'title': '全部接口测试',
            'opts': self.model._meta,
            'media': self.media,
            'endpoints': endpoints,
            'selected_method': method,
            'selected_path': path,
            'query_string': query,
            'headers_text': headers_raw,
            'body_text': body_raw,
            'body_format': body_format,
            'endpoint': endpoint_url,
            'http_status': http_status,
            'result_text': result_text,
            'result_kind': result_kind,
            'form_error': form_error,
            'elapsed_ms': elapsed_ms,
            'response_headers': response_headers,
            'curl_command': curl_command,
            'http_methods': canonical_order,
            'method_pills': method_pills,
            'body_formats': [
                ('json', 'JSON'),
                ('form', 'x-www-form-urlencoded'),
                ('text', 'Plain text'),
                ('none', '无 body'),
            ],
        }
        if extra_context:
            context.update(extra_context)
        return TemplateResponse(request, self.change_list_template, context)

    def _has_admin_access(self, request) -> bool:
        user = request.user
        return bool(user and user.is_active and user.is_staff)

    def _build_call(
        self,
        *,
        method: str,
        path: str,
        query: str,
        headers_raw: str,
        body_raw: str,
        body_format: str,
    ) -> tuple[str, bytes, str, dict[str, str]]:
        if not path:
            raise _FormError('请选择或输入接口路径')
        if not path.startswith('/'):
            raise _FormError('接口路径必须以 / 开头')
        if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'}:
            raise _FormError(f'不支持的 HTTP method: {method}')

        target_path = path
        if query:
            sep = '&' if '?' in target_path else '?'
            target_path = f'{target_path}{sep}{query.lstrip("?&")}'

        header_dict = self._parse_headers(headers_raw)

        if body_format == 'none' or method in {'GET', 'HEAD', 'DELETE', 'OPTIONS'} and not body_raw:
            return target_path, b'', '', header_dict

        if body_format == 'json':
            if not body_raw:
                return target_path, b'', '', header_dict
            try:
                parsed = json.loads(body_raw)
            except json.JSONDecodeError as exc:
                raise _FormError(f'Body 不是合法 JSON：{exc}') from exc
            payload = json.dumps(parsed, ensure_ascii=False).encode('utf-8')
            return target_path, payload, 'application/json', header_dict

        if body_format == 'form':
            try:
                pairs = self._parse_form_pairs(body_raw)
            except ValueError as exc:
                raise _FormError(f'Body form 格式错误：{exc}') from exc
            payload = urlencode(pairs).encode('utf-8')
            return target_path, payload, 'application/x-www-form-urlencoded', header_dict

        if body_format == 'text':
            return target_path, body_raw.encode('utf-8'), 'text/plain; charset=utf-8', header_dict

        raise _FormError(f'未知 body 格式：{body_format}')

    @staticmethod
    def _parse_headers(headers_raw: str) -> dict[str, str]:
        header_dict: dict[str, str] = {}
        for line in headers_raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if ':' not in stripped:
                raise _FormError(f'Header 行缺少冒号：{line!r}')
            name, value = stripped.split(':', 1)
            header_dict[name.strip()] = value.strip()
        return header_dict

    @staticmethod
    def _parse_form_pairs(body_raw: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        # 支持 key=value 多行 / 也支持单行 key1=v1&key2=v2
        if '\n' in body_raw:
            for line in body_raw.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if '=' not in stripped:
                    raise ValueError(f'缺少 = 号：{line!r}')
                k, v = stripped.split('=', 1)
                pairs.append((k.strip(), v))
        else:
            for chunk in body_raw.split('&'):
                if not chunk.strip():
                    continue
                if '=' not in chunk:
                    raise ValueError(f'缺少 = 号：{chunk!r}')
                k, v = chunk.split('=', 1)
                pairs.append((k.strip(), v))
        return pairs

    def _call_api(
        self,
        *,
        request,
        method: str,
        target_path: str,
        body_payload: bytes,
        content_type: str,
        header_dict: dict[str, str],
    ) -> tuple[int, str, str, int, list[tuple[str, str]]]:
        import time

        client = Client()
        client.force_login(request.user)

        # 把用户输入的 header 翻译成 Django Test Client 需要的 META 形式：
        # 'Authorization' -> 'HTTP_AUTHORIZATION'，Content-Type 单独传。
        extra: dict[str, Any] = {}
        for name, value in header_dict.items():
            normalized = name.upper().replace('-', '_')
            if normalized in {'CONTENT_TYPE', 'CONTENT_LENGTH'}:
                extra[normalized] = value
            else:
                extra[f'HTTP_{normalized}'] = value

        kwargs: dict[str, Any] = {}
        if body_payload:
            kwargs['data'] = body_payload
            kwargs['content_type'] = content_type or 'application/octet-stream'

        start = time.perf_counter()
        try:
            raw_response = client.generic(method, target_path, **kwargs, **extra)
        except Exception as exc:  # noqa: BLE001 — 显示给用户调试
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return 0, f'请求过程抛出异常：\n\n{type(exc).__name__}: {exc}', 'text', elapsed_ms, []
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Django Test Client.generic 返回 HttpResponse / StreamingHttpResponse，
        # 但 stub 错把返回值标成 WSGIRequest，先 cast 到 object 再到 Any 绕开。
        response: Any = cast(Any, cast(object, raw_response))

        # 取响应内容（流式响应也要 join 成 bytes）
        if getattr(response, 'streaming', False):
            chunks: list[bytes] = []
            for chunk in response.streaming_content:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                else:
                    chunks.append(str(chunk).encode('utf-8'))
            raw_body = b''.join(chunks)
        else:
            raw_body = response.content

        resp_content_type = response.get('Content-Type', '') or ''
        resp_headers: list[tuple[str, str]] = list(response.items())

        kind = 'text'
        try:
            text = raw_body.decode('utf-8')
        except UnicodeDecodeError:
            text = f'<{len(raw_body)} bytes binary; content-type={resp_content_type!r}>'
            kind = 'binary'
            return response.status_code, text, kind, elapsed_ms, resp_headers

        if 'application/json' in resp_content_type or self._looks_like_json(text):
            try:
                parsed = json.loads(text) if text else None
                text = json.dumps(parsed, ensure_ascii=False, indent=2)
                kind = 'json'
            except json.JSONDecodeError:
                kind = 'text'
        elif 'text/html' in resp_content_type:
            kind = 'html'
        else:
            kind = 'text'

        return response.status_code, text, kind, elapsed_ms, resp_headers

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        stripped = text.lstrip()
        return stripped.startswith('{') or stripped.startswith('[')

    @staticmethod
    def _build_curl(
        method: str,
        path: str,
        header_dict: dict[str, str],
        body_raw: str,
        body_format: str,
    ) -> str:
        parts = [f"curl -X {method} '{path}'"]
        if header_dict:
            for name, value in header_dict.items():
                parts.append(f"-H '{name}: {value}'")
        if body_format == 'json' and body_raw:
            parts.append("-H 'Content-Type: application/json'")
            parts.append(f"--data-raw '{body_raw}'")
        elif body_format == 'form' and body_raw:
            parts.append("-H 'Content-Type: application/x-www-form-urlencoded'")
            parts.append(f"--data '{body_raw}'")
        elif body_format == 'text' and body_raw:
            parts.append("-H 'Content-Type: text/plain'")
            parts.append(f"--data-raw '{body_raw}'")
        return ' \\\n  '.join(parts)


class _FormError(ValueError):
    """ApiTesterAdmin 内部表单校验错误。"""
