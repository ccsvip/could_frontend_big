from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteDevices, CanUpdateDevices, CanViewDevices, IsSuperUser
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.services import get_request_tenant

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceGroup
from .realtime import publish_device_event_sync
from .serializers import (
    DeviceApplicationSerializer,
    DeviceActivationLogSerializer,
    DeviceAuthorizationCodeSerializer,
    DeviceAuthorizationRequestSerializer,
    DeviceBindSerializer,
    DeviceDetailSerializer,
    DeviceGroupSerializer,
    DeviceSerializer,
    DeviceStatsSerializer,
)

AUTHORIZATION_LOG_ACTIONS = {
    DeviceAuthLog.ACTION_ACTIVATE,
    DeviceAuthLog.ACTION_BIND,
    DeviceAuthLog.ACTION_IGNORE,
    DeviceAuthLog.ACTION_AUTHORIZE,
    DeviceAuthLog.ACTION_REVOKE,
}
DEFAULT_DEVICE_NAME = '待修改'

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
        enabled_status = self.request.query_params.get('enabledStatus', '').strip()
        if enabled_status == 'enabled':
            queryset = queryset.filter(is_enabled=True)
        if enabled_status == 'disabled':
            queryset = queryset.filter(is_enabled=False)
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


class DeviceAuthorizationRequestViewSet(viewsets.GenericViewSet):
    permission_classes = [IsSuperUser]
    serializer_class = DeviceAuthorizationRequestSerializer
    lookup_field = 'code'
    lookup_value_regex = '[^/]+'
    queryset = Device.objects.select_related('tenant', 'application', 'group').all()

    def get_queryset(self):
        activation_logs = DeviceAuthLog.objects.filter(
            action=DeviceAuthLog.ACTION_ACTIVATE,
        ).order_by('-created_at', '-id')
        queryset = (
            super()
            .get_queryset()
            .filter(auth_logs__action=DeviceAuthLog.ACTION_ACTIVATE)
            .prefetch_related(Prefetch('auth_logs', queryset=activation_logs, to_attr='activation_logs_for_request'))
            .distinct()
            .order_by('-updated_at', '-id')
        )
        binding_status = self.request.query_params.get('bindingStatus', '').strip()
        if binding_status == 'pending':
            queryset = queryset.filter(tenant__isnull=True, authorization_ignored_at__isnull=True)
        if binding_status == 'bound':
            queryset = queryset.filter(tenant__isnull=False)
        if binding_status == 'ignored':
            queryset = queryset.filter(tenant__isnull=True, authorization_ignored_at__isnull=False)
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(code__icontains=keyword) | Q(name__icontains=keyword))
        tenant_id = self.request.query_params.get('tenantId', '').strip()
        if tenant_id.isdigit():
            queryset = queryset.filter(tenant_id=int(tenant_id))
        return queryset

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='logs')
    def logs(self, request):
        queryset = DeviceAuthLog.objects.select_related('tenant', 'application', 'device').filter(
            action__in=AUTHORIZATION_LOG_ACTIONS,
        ).order_by('-created_at', '-id')
        tenant_id = request.query_params.get('tenantId', '').strip()
        if tenant_id.isdigit():
            queryset = queryset.filter(tenant_id=int(tenant_id))
        keyword = request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(code__icontains=keyword) | Q(device__name__icontains=keyword))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceActivationLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceActivationLogSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='authorizations')
    def authorizations(self, request):
        queryset = (
            Device.objects.select_related('tenant', 'application', 'group')
            .filter(tenant__isnull=False)
            .order_by('-updated_at', '-id')
        )
        tenant_id = request.query_params.get('tenantId', '').strip()
        if tenant_id.isdigit():
            queryset = queryset.filter(tenant_id=int(tenant_id))
        keyword = request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(code__icontains=keyword) | Q(name__icontains=keyword))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceAuthorizationRequestSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceAuthorizationRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='bind')
    def bind(self, request, code=None):
        device = get_object_or_404(Device.objects.select_related('tenant', 'application', 'group'), code=code)
        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save(device=device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_BIND, '设备已绑定到公司', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_BIND)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='ignore')
    def ignore(self, request, code=None):
        device = get_object_or_404(Device.objects.select_related('tenant', 'application', 'group'), code=code)
        device.authorization_ignored_at = timezone.now()
        device.save(update_fields=['authorization_ignored_at', 'updated_at'])
        self._log_platform_action(device, DeviceAuthLog.ACTION_IGNORE, '设备授权请求已忽略', request)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='name')
    def rename(self, request, code=None):
        device = get_object_or_404(Device.objects.select_related('tenant', 'application', 'group'), code=code)
        next_name = str(request.data.get('name') or '').strip()
        if not next_name:
            return Response({'name': '设备名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        device.name = next_name
        device.save(update_fields=['name', 'updated_at'])
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='authorize')
    def authorize(self, request, code=None):
        device = get_object_or_404(Device.objects.select_related('tenant', 'application', 'group'), code=code)
        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save(device=device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_AUTHORIZE, '设备已再次授权', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_AUTHORIZE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, code=None):
        device = get_object_or_404(Device.objects.select_related('tenant', 'application', 'group'), code=code)
        device.is_enabled = False
        device.status = Device.STATUS_OFFLINE
        device.save(update_fields=['is_enabled', 'status', 'updated_at'])
        self._log_platform_action(device, DeviceAuthLog.ACTION_REVOKE, '设备授权已撤销', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_REVOKE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @staticmethod
    def _log_platform_action(device, action, message, request):
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=device.application,
            device=device,
            code=device.code,
            action=action,
            result=True,
            message=message,
            ip_address=_client_ip(request),
            device_info={
                'tenantId': device.tenant_id,
                'applicationId': device.application_id,
                'groupId': device.group_id,
                'authorizationType': device.authorization_type,
                'expiresAt': device.expires_at.isoformat() if device.expires_at else None,
                'isEnabled': device.is_enabled,
            },
        )

    @staticmethod
    def _publish_authorization_event(device, action):
        publish_device_event_sync(
            {
                'type': 'device.authorization',
                'action': action,
                'tenantId': device.tenant_id,
                'applicationId': device.application_id,
                'groupId': device.group_id,
                'deviceCode': device.code,
                'status': device.status,
                'isEnabled': device.is_enabled,
            }
        )


class DeviceActivationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Device Runtime'])
    @transaction.atomic
    def post(self, request):
        device_code = str(request.data.get('deviceCode') or request.data.get('device_code') or '').strip()
        if not device_code:
            self._log_activation(None, '', False, '设备码不能为空', request)
            return Response({'message': '设备码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        existing_devices = list(
            Device.objects.select_for_update()
            .filter(code=device_code)
            .order_by('id')[:2]
        )
        if len(existing_devices) > 1:
            self._log_activation(None, device_code, False, '设备码存在重复绑定，请联系后台处理', request)
            return Response({'message': '设备码存在重复绑定，请联系后台处理'}, status=status.HTTP_409_CONFLICT)

        now = timezone.now()
        device_info = request.data.get('deviceInfo') or request.data.get('device_info') or {}
        defaults = {
            'software_version': str(request.data.get('softwareVersion') or request.data.get('software_version') or '').strip(),
            'system_version': str(request.data.get('systemVersion') or request.data.get('system_version') or '').strip(),
            'mainboard_info': str(request.data.get('mainboardInfo') or request.data.get('mainboard_info') or '').strip(),
            'registered_at': now,
            'last_auth_at': now,
            'last_heartbeat': now,
            'authorization_ignored_at': None,
            'device_info': device_info,
        }
        if existing_devices:
            device = existing_devices[0]
            for field, value in defaults.items():
                setattr(device, field, value)
            device.save(update_fields=[*defaults.keys(), 'updated_at'])
            message = '设备上报成功'
        else:
            device = Device.objects.create(
                code=device_code,
                name=DEFAULT_DEVICE_NAME,
                authorization_type=Device.AUTHORIZATION_PERMANENT,
                is_enabled=True,
                **defaults,
            )
            message = '设备上报成功，待后台绑定应用'
        self._log_activation(device, device_code, True, message, request)
        return Response(
            {
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': self._application_payload(device.application),
                'bindingStatus': 'bound' if device.application_id and device.tenant_id else 'pending',
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _application_payload(application):
        if application is None:
            return None
        return {
            'id': application.id,
            'name': application.name,
            'code': application.code,
        }

    @staticmethod
    def _log_activation(device, device_code, result, message, request):
        raw_device_info = request.data.get('deviceInfo') or request.data.get('device_info') or {}
        device_info = raw_device_info if isinstance(raw_device_info, dict) else {'raw': raw_device_info}
        device_info = {
            **device_info,
            'softwareVersion': request.data.get('softwareVersion') or request.data.get('software_version') or '',
            'systemVersion': request.data.get('systemVersion') or request.data.get('system_version') or '',
            'mainboardInfo': request.data.get('mainboardInfo') or request.data.get('mainboard_info') or '',
        }
        DeviceAuthLog.objects.create(
            tenant=getattr(device, 'tenant', None),
            application=getattr(device, 'application', None),
            device=device,
            code=device_code,
            action=DeviceAuthLog.ACTION_ACTIVATE,
            result=result,
            message=message,
            ip_address=_client_ip(request),
            device_info=device_info,
        )


class DeviceRuntimeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_device_code(self, request) -> str:
        return str(
            request.data.get('deviceCode')
            or request.data.get('device_code')
            or request.query_params.get('deviceCode')
            or request.query_params.get('device_code')
            or request.headers.get('X-Device-Code')
            or ''
        ).strip()

    def validate_device(self, request):
        device_code = self.get_device_code(request)
        if not device_code:
            return None, Response({'message': '设备码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        devices = list(
            Device.objects.select_related('tenant', 'application')
            .filter(code=device_code)
            .order_by('id')[:2]
        )
        if not devices:
            return None, Response({'message': '设备未登记'}, status=status.HTTP_404_NOT_FOUND)
        if len(devices) > 1:
            return None, Response({'message': '设备码存在重复绑定，请联系后台处理'}, status=status.HTTP_409_CONFLICT)
        device = devices[0]
        if device.tenant is not None and not device.tenant.is_active:
            return None, Response({'message': '公司已停用'}, status=status.HTTP_403_FORBIDDEN)
        if not device.is_enabled:
            return None, Response({'message': '设备已停用'}, status=status.HTTP_403_FORBIDDEN)
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
        update_fields = ['last_heartbeat', 'updated_at']
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
