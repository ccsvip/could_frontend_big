from __future__ import annotations

import re
from urllib.parse import quote

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import parsers, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperUser
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device
from config.request_id import get_request_id, get_trace_id

from .models import AppRelease
from .serializers import AppReleaseManagementSerializer, AppUpdateCheckSerializer, AppUpdateReportSerializer
from .signing import AppUpdateSigningError, sign_release


def _trace_payload(request, **payload):
    return {'requestId': get_request_id(request), 'traceId': get_trace_id(request), **payload}


def _error_response(request, *, code: str, message: str, http_status: int, details=None):
    payload = _trace_payload(request, code=code, message=message)
    if details is not None:
        payload['details'] = details
    return Response(payload, status=http_status)


def _runtime_device(request):
    return get_runtime_device(request.headers.get('X-Device-Code', ''), require_tenant=True)


class AppReleaseViewSet(viewsets.ModelViewSet):
    serializer_class = AppReleaseManagementSerializer
    permission_classes = [IsSuperUser]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    lookup_field = 'release_id'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return AppRelease.objects.select_related('created_by').all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                request,
                code='INVALID_REQUEST',
                message='发布字段错误',
                http_status=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppUpdateCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            _runtime_device(request)
        except RuntimeDeviceError as exc:
            return _error_response(request, code=exc.code, message=exc.message, http_status=exc.status_code)

        serializer = AppUpdateCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                request, code='INVALID_REQUEST', message='请求字段错误',
                http_status=status.HTTP_400_BAD_REQUEST, details=serializer.errors,
            )

        latest = AppRelease.objects.filter(is_active=True).order_by('-version_code').first()
        if latest is None:
            return Response(_trace_payload(request, hasUpdate=False, forceUpgradeVersionCode=0, release=None))

        current_version = serializer.validated_data['versionCode']
        threshold = latest.force_upgrade_version_code
        if latest.version_code <= current_version:
            return Response(_trace_payload(
                request, hasUpdate=False, forceUpgradeVersionCode=threshold, release=None,
            ))

        download_url = request.build_absolute_uri(f'/api/v1/app-update-releases/{latest.release_id}/apk/')
        try:
            signed = sign_release(latest, download_url=download_url, force_upgrade_version_code=threshold)
        except AppUpdateSigningError as exc:
            return _error_response(
                request, code='UPDATE_SIGNING_UNAVAILABLE', message=str(exc),
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(_trace_payload(
            request,
            hasUpdate=True,
            forceUpgradeVersionCode=threshold,
            release={
                'releaseId': latest.release_id,
                'packageName': latest.package_name,
                'versionName': latest.version_name,
                'versionCode': latest.version_code,
                'versionInfo': latest.version_info,
                'fileName': latest.file_name,
                'downloadUrl': download_url,
                'fileSize': latest.file_size,
                'sha256': latest.sha256,
                'signature': signed.signature,
                'expiresAt': signed.expires_at,
                'releaseNotes': latest.release_notes,
            },
        ))


class AppUpdateReportView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            device = _runtime_device(request)
        except RuntimeDeviceError as exc:
            return _error_response(request, code=exc.code, message=exc.message, http_status=exc.status_code)
        serializer = AppUpdateReportSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                request, code='INVALID_REQUEST', message='请求字段错误',
                http_status=status.HTTP_400_BAD_REQUEST, details=serializer.errors,
            )
        event = serializer.create_event(device=device)
        return Response(_trace_payload(request, eventId=event.id), status=status.HTTP_201_CREATED)


def _file_chunks(file_field, start: int, length: int, chunk_size: int = 1024 * 1024):
    with file_field.open('rb') as stream:
        stream.seek(start)
        remaining = length
        while remaining > 0:
            data = stream.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


class AppReleaseDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    RANGE_PATTERN = re.compile(r'^bytes=(\d*)-(\d*)$')

    def get(self, request, release_id: str):
        release = get_object_or_404(AppRelease, release_id=release_id, is_active=True)
        size = release.file_size
        start, end = 0, size - 1
        response_status = status.HTTP_200_OK
        range_header = str(request.headers.get('Range') or '').strip()
        if range_header:
            match = self.RANGE_PATTERN.fullmatch(range_header)
            if not match or ',' in range_header:
                return self._range_not_satisfiable(size)
            first, last = match.groups()
            if not first and not last:
                return self._range_not_satisfiable(size)
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                suffix_length = int(last)
                if suffix_length <= 0:
                    return self._range_not_satisfiable(size)
                start = max(0, size - suffix_length)
                end = size - 1
            if start >= size or start > end:
                return self._range_not_satisfiable(size)
            response_status = status.HTTP_206_PARTIAL_CONTENT

        length = end - start + 1
        response = StreamingHttpResponse(
            _file_chunks(release.apk_file, start, length),
            status=response_status,
            content_type='application/vnd.android.package-archive',
        )
        response['Content-Length'] = str(length)
        response['Accept-Ranges'] = 'bytes'
        response['ETag'] = f'"{release.sha256}"'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(release.file_name)}"
        if response_status == status.HTTP_206_PARTIAL_CONTENT:
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
        return response

    @staticmethod
    def _range_not_satisfiable(size: int):
        response = Response(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
        response['Content-Range'] = f'bytes */{size}'
        response['Accept-Ranges'] = 'bytes'
        return response
