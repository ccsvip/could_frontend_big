from __future__ import annotations

import uuid
from typing import Any


REQUEST_ID_HEADER = 'X-Request-ID'
TRACE_ID_HEADER = 'X-Trace-ID'


def make_request_id() -> str:
    return uuid.uuid4().hex


def clean_trace_value(value: Any) -> str:
    if value is None:
        return ''
    return str(value).replace('\r', '').replace('\n', '').strip()[:128]


def _clean_header_value(value: Any) -> str:
    return clean_trace_value(value)


class RequestIdMiddleware:
    """Attach a stable request/trace id to every HTTP request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = _clean_header_value(request.headers.get(REQUEST_ID_HEADER)) or make_request_id()
        trace_id = _clean_header_value(request.headers.get(TRACE_ID_HEADER)) or request_id
        request.request_id = request_id
        request.trace_id = trace_id

        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        response[TRACE_ID_HEADER] = trace_id
        return response


def get_request_id(request) -> str:
    return _clean_header_value(getattr(request, 'request_id', ''))


def get_trace_id(request) -> str:
    return _clean_header_value(getattr(request, 'trace_id', '')) or get_request_id(request)
