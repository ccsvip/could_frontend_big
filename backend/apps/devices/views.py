from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteDevices, CanUpdateDevices, CanViewDevices
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.services import get_request_tenant

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceGroup
from .serializers import (
    DeviceApplicationSerializer,
    DeviceAuthorizationCodeSerializer,
    DeviceDetailSerializer,
    DeviceGroupSerializer,
    DeviceSerializer,
    DeviceStatsSerializer,
)
from .tokens import make_device_token, resolve_device_token


def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class DevicePermissionMixin:
    def get_permissions(self):
        permission_map = {
            'list': [CanViewDevices],
            'retrieve': [CanViewDevices],
            'stats': [CanViewDevices],
            'create': [CanCreateDevices],
            'update': [CanUpdateDevices],
            'partial_update': [CanUpdateDevices],
            'destroy': [CanDeleteDevices],
        }
        permission_classes = permission_map.get(getattr(self, 'action', None), [CanViewDevices])
        if getattr(self, 'action', None) in {'create', 'update', 'partial_update', 'destroy'}:
            permission_classes = [CompanyDeviceWritePermission, *permission_classes]
        return [permission() for permission in permission_classes]


class CompanyDeviceWritePermission(BasePermission):
    message = '设备属于公司，请使用公司账号管理设备资源'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or user.is_superuser:
            return False
        return get_request_tenant(request) is not None


@extend_schema_view(
    list=extend_schema(tags=['Devices']),
    retrieve=extend_schema(tags=['Devices']),
    create=extend_schema(tags=['Devices']),
    update=extend_schema(tags=['Devices']),
    partial_update=extend_schema(tags=['Devices']),
    destroy=extend_schema(tags=['Devices']),
)
class DeviceViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Device.objects.select_related('application', 'group').all()
    lookup_field = 'code'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        return DeviceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter in {Device.STATUS_ONLINE, Device.STATUS_OFFLINE}:
            queryset = queryset.filter(status=status_filter)
        authorization_type = self.request.query_params.get('authorizationType', '').strip()
        if authorization_type in {Device.AUTHORIZATION_PERMANENT, Device.AUTHORIZATION_TRIAL}:
            queryset = queryset.filter(authorization_type=authorization_type)
        group_id = self.request.query_params.get('groupId', '').strip()
        if group_id.isdigit():
            queryset = queryset.filter(group_id=int(group_id))
        application_id = self.request.query_params.get('applicationId', '').strip()
        if application_id.isdigit():
            queryset = queryset.filter(application_id=int(application_id))
        return queryset

    @extend_schema(responses=DeviceStatsSerializer, tags=['Devices'])
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_superuser:
            scoped_tenant_id = self.superuser_tenant_filter()
            cache_key = (
                f'device_stats:scoped:{scoped_tenant_id}'
                if scoped_tenant_id is not None
                else 'device_stats:all'
            )
        else:
            tenant = self.request_tenant
            cache_key = f'device_stats:{tenant.id if tenant else "all"}'
        stats = cache.get(cache_key)
        if not stats:
            queryset = self.get_queryset()
            grouped = queryset.values('status').annotate(total=Count('id'))
            auth_grouped = queryset.values('authorization_type').annotate(total=Count('id'))
            stats = {
                'total': queryset.count(),
                'online': 0,
                'offline': 0,
                'trial': 0,
                'permanent': 0,
            }
            for item in grouped:
                if item['status'] in {'online', 'offline'}:
                    stats[item['status']] = item['total']
            for item in auth_grouped:
                if item['authorization_type'] == Device.AUTHORIZATION_TRIAL:
                    stats['trial'] = item['total']
                if item['authorization_type'] == Device.AUTHORIZATION_PERMANENT:
                    stats['permanent'] = item['total']
            cache.set(cache_key, stats, timeout=300)
        return Response(stats)


class DeviceGroupViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceGroup.objects.all()
    serializer_class = DeviceGroupSerializer


class DeviceApplicationViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceApplication.objects.prefetch_related(
        'resources',
        'scrolling_texts__items',
        'voice_tones',
        'model_assets',
        'command_groups',
    ).all()
    serializer_class = DeviceApplicationSerializer


class DeviceAuthorizationCodeViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceAuthorizationCode.objects.select_related('application', 'used_by_device').all()
    serializer_class = DeviceAuthorizationCodeSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        serializer.save(**self.tenant_create_kwargs())


class DeviceActivationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Device Runtime'])
    @transaction.atomic
    def post(self, request):
        auth_code_value = str(request.data.get('authCode') or request.data.get('auth_code') or '').strip()
        device_code = str(request.data.get('deviceCode') or request.data.get('device_code') or '').strip()
        if not auth_code_value:
            return Response({'message': '授权码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if not device_code:
            return Response({'message': '设备码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        auth_code = (
            DeviceAuthorizationCode.objects.select_for_update()
            .select_related('application')
            .filter(code=auth_code_value)
            .first()
        )
        if auth_code is None:
            self._log_activation(None, None, auth_code_value, device_code, False, '授权码不存在', request)
            return Response({'message': '授权码不存在'}, status=status.HTTP_400_BAD_REQUEST)
        if not auth_code.is_available:
            self._log_activation(auth_code, None, auth_code_value, device_code, False, '授权码不可用', request)
            return Response({'message': '授权码已使用、禁用或过期'}, status=status.HTTP_400_BAD_REQUEST)
        if auth_code.tenant and not auth_code.tenant.is_active:
            self._log_activation(auth_code, None, auth_code_value, device_code, False, '公司已停用', request)
            return Response({'message': '公司已停用'}, status=status.HTTP_400_BAD_REQUEST)
        if not auth_code.application.is_active:
            self._log_activation(auth_code, None, auth_code_value, device_code, False, '应用已停用', request)
            return Response({'message': '应用已停用'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        device, _created = Device.objects.update_or_create(
            tenant=auth_code.tenant,
            code=device_code,
            defaults={
                'application': auth_code.application,
                'name': str(request.data.get('deviceName') or request.data.get('device_name') or device_code).strip(),
                'status': Device.STATUS_ONLINE,
                'authorization_type': auth_code.authorization_type,
                'expires_at': auth_code.expires_at,
                'software_version': str(request.data.get('softwareVersion') or request.data.get('software_version') or '').strip(),
                'system_version': str(request.data.get('systemVersion') or request.data.get('system_version') or '').strip(),
                'mainboard_info': str(request.data.get('mainboardInfo') or request.data.get('mainboard_info') or '').strip(),
                'is_enabled': True,
                'registered_at': now,
                'last_auth_at': now,
                'last_heartbeat': now,
                'device_info': request.data.get('deviceInfo') or request.data.get('device_info') or {},
            },
        )
        auth_code.status = DeviceAuthorizationCode.STATUS_USED
        auth_code.used_at = now
        auth_code.used_by_device = device
        auth_code.save(update_fields=['status', 'used_at', 'used_by_device', 'updated_at'])
        self._log_activation(auth_code, device, auth_code_value, device_code, True, '激活成功', request)
        return Response(
            {
                'token': make_device_token(device),
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': {
                    'id': auth_code.application.id,
                    'name': auth_code.application.name,
                    'code': auth_code.application.code,
                },
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _log_activation(auth_code, device, auth_code_value, device_code, result, message, request):
        DeviceAuthLog.objects.create(
            tenant=getattr(auth_code, 'tenant', None),
            application=getattr(auth_code, 'application', None),
            auth_code=auth_code,
            device=device,
            code=device_code,
            action=DeviceAuthLog.ACTION_ACTIVATE,
            result=result,
            message=message,
            ip_address=_client_ip(request),
            device_info=request.data.get('deviceInfo') or request.data.get('device_info') or {'authCode': auth_code_value},
        )


class DeviceRuntimeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def resolve_device(self, request):
        raw = request.headers.get('Authorization', '')
        prefix = 'Bearer '
        if not raw.startswith(prefix):
            return None
        return resolve_device_token(raw[len(prefix):].strip())

    def validate_device(self, request):
        device = self.resolve_device(request)
        if device is None:
            return None, Response({'message': '设备 token 无效'}, status=status.HTTP_401_UNAUTHORIZED)
        if not device.is_enabled:
            return None, Response({'message': '设备已禁用'}, status=status.HTTP_403_FORBIDDEN)
        if device.is_expired:
            return None, Response({'message': '设备授权已过期'}, status=status.HTTP_403_FORBIDDEN)
        return device, None


class DeviceRuntimeConfigView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def get(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        application = device.application
        if application is None or not application.is_active:
            return Response({'message': '设备未绑定可用应用'}, status=status.HTTP_403_FORBIDDEN)
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_CONFIG,
            result=True,
            message='配置拉取成功',
            ip_address=_client_ip(request),
        )
        return Response(
            {
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': {
                    'id': application.id,
                    'name': application.name,
                    'code': application.code,
                },
                'resources': self._resources_payload(application, request),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _resources_payload(application: DeviceApplication, request):
        def file_url(file_field):
            if not file_field:
                return ''
            return request.build_absolute_uri(file_field.url)

        resources = application.resources.all()
        return {
            'images': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': item.cloud_url or file_url(item.file),
                    'category': item.category,
                }
                for item in resources
                if item.resource_type == item.TYPE_IMAGE
            ],
            'videos': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': item.cloud_url or file_url(item.file),
                    'category': item.category,
                }
                for item in resources
                if item.resource_type == item.TYPE_VIDEO
            ],
            'scrollingTexts': [
                {
                    'id': item.id,
                    'title': item.title,
                    'i18nScheme': item.i18n_scheme,
                    'items': [
                        {
                            'id': text_item.id,
                            'order': text_item.order,
                            'zh': text_item.zh_text,
                            'en': text_item.en_text,
                        }
                        for text_item in item.items.all()
                    ],
                }
                for item in application.scrolling_texts.filter(is_active=True).prefetch_related('items')
            ],
            'voiceTones': [
                {
                    'id': item.id,
                    'name': item.name,
                    'voiceCode': item.voice_code,
                    'audioUrl': file_url(item.audio),
                    'iconUrl': file_url(item.icon),
                }
                for item in application.voice_tones.filter(is_active=True, is_visible=True)
            ],
            'models': [
                {
                    'id': item.id,
                    'name': item.name,
                    'modelType': item.model_type,
                    'orientation': item.orientation,
                    'url': item.cloud_url or file_url(item.model_file),
                    'thumbnailUrl': file_url(item.thumbnail),
                }
                for item in application.model_assets.filter(is_visible=True)
            ],
            'commandGroups': [
                {
                    'id': item.id,
                    'name': item.name,
                    'groupType': item.group_type,
                }
                for item in application.command_groups.filter(is_active=True)
            ],
        }


class DeviceRuntimeHeartbeatView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def post(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        update_fields = ['status', 'last_heartbeat', 'updated_at']
        device.status = Device.STATUS_ONLINE
        device.last_heartbeat = timezone.now()
        software_version = str(request.data.get('softwareVersion') or request.data.get('software_version') or '').strip()
        system_version = str(request.data.get('systemVersion') or request.data.get('system_version') or '').strip()
        if software_version:
            device.software_version = software_version
            update_fields.append('software_version')
        if system_version:
            device.system_version = system_version
            update_fields.append('system_version')
        device.save(update_fields=update_fields)
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=device.application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_HEARTBEAT,
            result=True,
            message='心跳成功',
            ip_address=_client_ip(request),
            device_info=request.data.get('deviceInfo') or request.data.get('device_info') or {},
        )
        return Response({'status': 'success', 'message': '心跳成功'}, status=status.HTTP_200_OK)
