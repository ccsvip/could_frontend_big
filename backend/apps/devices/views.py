from __future__ import annotations

import base64
import logging
import uuid

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteChat, CanDeleteDevices, CanUpdateDevices, CanViewChat, CanViewDevices, IsSuperUser
from apps.ai_models import llm_services
from apps.ai_models.models import AgentAnnotation, ChatConversation, LLMModel, RUNTIME_BACKEND_THIRD_PARTY_CHATBOT, ThirdPartyChatbotApplication
from apps.ai_models.services.annotations import find_matching_annotation, find_matching_published_annotation
from apps.ai_models.services.reply_blocks import blocks_to_text, serialize_published_annotation_blocks, serialize_reply_blocks, text_to_blocks
from apps.ai_models.services import asr as asr_services
from apps.ai_models.services import third_party_chatbots
from apps.ai_models.services import tts as tts_services
from apps.resources.models import ModelAsset, Resource, ScrollingText
from apps.resources.services.minio_client import build_public_object_url
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.services import get_request_tenant
from config.request_id import get_request_id, get_trace_id

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceChatLog, DeviceGroup, WakeWord
from .realtime import publish_device_event_sync
from .services.chat_logs import record_device_chat_log
from .services.chat_sessions import (
    device_chat_session_groups,
    device_chat_session_logs,
    serialize_device_chat_session,
    serialize_device_chat_session_groups,
)
from .services import session_store
from .services.authorization import (
    bind_device_authorization,
    ignore_device_authorization_request,
    publish_device_authorization_event,
    record_device_authorization_action,
    rename_authorization_device,
    revoke_device_authorization,
)
from .services.queries import (
    device_authorization_logs_queryset,
    device_authorization_requests_queryset,
    device_authorizations_queryset,
    device_chat_logs_queryset,
)
from .services.runtime import (
    RUNTIME_ERROR_AGENT_UNBOUND,
    RUNTIME_ERROR_DEVICE_EXPIRED,
    RUNTIME_ERROR_DUPLICATE_DEVICE_CODE,
    RUNTIME_ERROR_EMPTY_DEVICE_CODE,
    RuntimeDeviceError,
    get_runtime_device,
    runtime_device_error,
    validate_runtime_application_active,
)
from .services.voice_pipeline_logging import log_voice_pipeline
from .tts_voice_config import device_tts_session_config, public_device_tts_voice_config
from .serializers import (
    DeviceApplicationSerializer,
    DeviceActivationLogSerializer,
    DeviceAuthorizationCodeSerializer,
    DeviceAuthorizationRequestSerializer,
    DeviceBindSerializer,
    DeviceChatLogSerializer,
    DeviceDetailSerializer,
    DeviceGroupSerializer,
    DeviceSerializer,
    DeviceStatsSerializer,
    WakeWordSerializer,
)

DEFAULT_DEVICE_NAME = '待修改'
logger = logging.getLogger(__name__)


def _log_http_voice_pipeline(stage: str, context: dict[str, str | None], payload: dict) -> None:
    log_voice_pipeline(
        logger,
        'device.voice_chat.pipeline',
        stage,
        command_id=context.get('sessionId'),
        request_id=context['requestId'] or '',
        trace_id=context['traceId'] or '',
        device_code=context['deviceCode'] or '',
        payload=payload,
    )

def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class DeviceChatSessionCollectionView(TenantScopedQuerysetMixin, generics.GenericAPIView):
    permission_classes = [CanViewChat]

    def get_permissions(self):
        permission_class = CanDeleteChat if self.request.method == 'DELETE' else CanViewChat
        return [permission_class()]

    def get_queryset(self):
        return self.apply_tenant_scope(device_chat_logs_queryset(self.request.query_params))

    def validate_application_scope(self):
        application_id = str(self.request.query_params.get('agentApplicationId') or '').strip()
        if not application_id.isdigit():
            raise ValidationError({'agentApplicationId': '设备运行时历史必须指定智能体应用'})

    def get(self, request):
        self.validate_application_scope()
        queryset = self.get_queryset()
        groups = device_chat_session_groups(queryset)
        page = self.paginate_queryset(groups)
        if page is not None:
            data = serialize_device_chat_session_groups(list(page), queryset)
            return self.get_paginated_response(data)
        return Response(serialize_device_chat_session_groups(list(groups), queryset))

    def delete(self, request):
        self.validate_application_scope()
        self.get_queryset().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceChatSessionDetailView(TenantScopedQuerysetMixin, generics.GenericAPIView):
    permission_classes = [CanViewChat]

    def get_permissions(self):
        permission_class = CanDeleteChat if self.request.method == 'DELETE' else CanViewChat
        return [permission_class()]

    def get_queryset(self):
        return self.apply_tenant_scope(device_chat_logs_queryset())

    def get(self, request, pk: int):
        queryset = self.get_queryset()
        seed = get_object_or_404(queryset, id=pk)
        logs = list(
            device_chat_session_logs(queryset, seed).select_related(
                'tenant',
                'device',
                'conversation__llm_model__provider',
                'conversation__third_party_chatbot__provider',
            )
        )
        return Response(serialize_device_chat_session(logs, request=request))

    def delete(self, request, pk: int):
        queryset = self.get_queryset()
        seed = get_object_or_404(queryset, id=pk)
        with transaction.atomic():
            device_chat_session_logs(queryset, seed).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    queryset = Device.objects.select_related('application__agent_application', 'agent_application', 'tts_voice__provider', 'group').all()
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

    @staticmethod
    def _publish_runtime_config_changed(device: Device, action: str) -> None:
        payload = {
            'type': 'device.voice_configuration.changed',
            'action': action,
            'operation': 'update',
            'resource': 'voiceConfiguration',
            'tenantId': device.tenant_id,
            'deviceCode': device.code,
            'deviceCodes': [device.code],
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': action,
            },
        }
        transaction.on_commit(lambda: publish_device_event_sync(payload))

    def perform_update(self, serializer):
        previous_voice_id = serializer.instance.tts_voice_id
        previous_voice_config = dict(serializer.instance.tts_voice_config or {})
        device = serializer.save()
        if previous_voice_id != device.tts_voice_id or previous_voice_config != dict(device.tts_voice_config or {}):
            self._publish_runtime_config_changed(device, 'voiceConfigurationChanged')

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

    @action(detail=False, methods=['get'], url_path='chat-logs')
    def chat_logs(self, request):
        queryset = self.apply_tenant_scope(device_chat_logs_queryset(request.query_params))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceChatLogSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = DeviceChatLogSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class DeviceGroupViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceGroup.objects.all()
    serializer_class = DeviceGroupSerializer


class DeviceApplicationViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceApplication.objects.select_related('agent_application').prefetch_related(
        'resources',
        'scrolling_texts__items',
        'voice_tones',
        'tts_voices',
        'model_assets',
        'command_groups',
    ).all()
    serializer_class = DeviceApplicationSerializer

    def get_permissions(self):
        if self.action == 'deletion_impact':
            return [CompanyDeviceWritePermission(), CanDeleteDevices()]
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='deletion-impact')
    def deletion_impact(self, request, pk=None):
        application = self.get_object()
        return Response({
            'deviceCount': application.devices.filter(tenant_id=application.tenant_id).count(),
            'authorizationCodeCount': application.authorization_codes.filter(tenant_id=application.tenant_id).count(),
        })

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        application = self.get_object()
        application = self.apply_tenant_scope(DeviceApplication.objects.all()).select_for_update().get(pk=application.pk)
        devices = list(Device.objects.select_for_update().filter(application=application, tenant_id=application.tenant_id))
        authorization_codes = DeviceAuthorizationCode.objects.select_for_update().filter(
            application=application,
            tenant_id=application.tenant_id,
        )
        device_codes = [device.code for device in devices]
        tenant_id = application.tenant_id

        Device.objects.filter(id__in=[device.id for device in devices], tenant_id=tenant_id).update(application=None)
        authorization_codes.update(application=None)
        application.delete()

        if device_codes:
            payload = {
                'type': 'device.application.changed',
                'action': 'applicationDeleted',
                'operation': 'update',
                'resource': 'application',
                'tenantId': tenant_id,
                'deviceCodes': device_codes,
                'refresh': {
                    'endpoint': '/api/v1/device-runtime/config/',
                    'reason': 'applicationDeleted',
                },
            }
            transaction.on_commit(lambda: publish_device_event_sync(payload))
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    queryset = Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'group').all()

    def get_queryset(self):
        return device_authorization_requests_queryset(self.request.query_params)

    def get_authorization_device(self, code) -> Device:
        devices = list(
            Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'group')
            .filter(code=code)
            .order_by('id')[:2]
        )
        if not devices:
            raise Http404
        if len(devices) > 1:
            conflict = APIException('设备码存在重复绑定，请先清理重复设备记录')
            conflict.status_code = status.HTTP_409_CONFLICT
            raise conflict
        return devices[0]

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
        queryset = device_authorization_logs_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceActivationLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceActivationLogSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='authorizations')
    def authorizations(self, request):
        queryset = device_authorizations_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceAuthorizationRequestSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceAuthorizationRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='bind')
    def bind(self, request, code=None):
        device = self.get_authorization_device(code)
        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = bind_device_authorization(device, serializer)
        self._log_platform_action(device, DeviceAuthLog.ACTION_BIND, '设备已绑定到公司', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_BIND)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='ignore')
    def ignore(self, request, code=None):
        device = self.get_authorization_device(code)
        device = ignore_device_authorization_request(device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_IGNORE, '设备授权请求已忽略', request)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='name')
    def rename(self, request, code=None):
        device = self.get_authorization_device(code)
        next_name = str(request.data.get('name') or '').strip()
        if not next_name:
            return Response({'name': '设备名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        device = rename_authorization_device(device, next_name)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='authorize')
    def authorize(self, request, code=None):
        device = self.get_authorization_device(code)
        if device.tenant_id is None:
            return Response({'tenantId': '未绑定公司的设备请使用绑定操作'}, status=status.HTTP_400_BAD_REQUEST)

        requested_tenant_id = request.data.get('tenantId')
        if str(requested_tenant_id) != str(device.tenant_id):
            return Response({'tenantId': '再次授权不能变更所属公司'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = bind_device_authorization(device, serializer)
        self._log_platform_action(device, DeviceAuthLog.ACTION_AUTHORIZE, '设备已再次授权', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_AUTHORIZE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, code=None):
        device = self.get_authorization_device(code)
        device = revoke_device_authorization(device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_REVOKE, '设备授权已撤销', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_REVOKE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @transaction.atomic
    def destroy(self, request, code=None):
        device = self.get_authorization_device(code)
        tenant_id = device.tenant_id
        device_code = device.code
        device.delete()

        transaction.on_commit(lambda: publish_device_event_sync({
            'type': 'device.authorization',
            'action': 'deviceDeleted',
            'tenantId': tenant_id,
            'deviceCode': device_code,
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': 'deviceDeleted',
            },
        }))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _log_platform_action(device, action, message, request):
        record_device_authorization_action(device, action, message, ip_address=_client_ip(request))

    @staticmethod
    def _publish_authorization_event(device, action):
        publish_device_authorization_event(device, action)


class DeviceActivationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Device Runtime'])
    @transaction.atomic
    def post(self, request):
        device_code = str(
            request.headers.get('X-Device-Code')
            or request.data.get('deviceCode')
            or request.data.get('device_code')
            or ''
        ).strip()
        if not device_code:
            self._log_activation(None, '', False, '设备码不能为空', request)
            error = runtime_device_error('设备码不能为空', status.HTTP_400_BAD_REQUEST, RUNTIME_ERROR_EMPTY_DEVICE_CODE)
            return Response(error.as_payload(), status=error.status_code)
        existing_devices = list(
            Device.objects.select_for_update()
            .filter(code=device_code)
            .order_by('id')[:2]
        )
        if len(existing_devices) > 1:
            self._log_activation(None, device_code, False, '设备码存在重复绑定，请联系后台处理', request)
            error = runtime_device_error('设备码存在重复绑定，请联系后台处理', status.HTTP_409_CONFLICT, RUNTIME_ERROR_DUPLICATE_DEVICE_CODE)
            return Response(error.as_payload(), status=error.status_code)

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
            message = '设备上报成功，待后台绑定公司'
        self._log_activation(device, device_code, True, message, request)
        return Response(
            {
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': self._application_payload(device.application),
                'agentApplication': self._agent_application_payload(device.agent_application),
                'bindingStatus': 'bound' if device.tenant_id else 'pending',
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
    def _agent_application_payload(agent_application):
        if agent_application is None:
            return None
        config = agent_application.runtime_config()
        llm_model_id = config.get('llm_model_id')
        model_name = agent_application.model_name
        if llm_model_id != agent_application.llm_model_id:
            model_name = LLMModel.objects.filter(id=llm_model_id).values_list('name', flat=True).first() or ''
        return {
            'id': agent_application.id,
            'name': config.get('name') or agent_application.name,
            'llmModelId': llm_model_id,
            'llmModelName': model_name,
            'publishedAt': agent_application.published_at,
            'publishedVersion': agent_application.published_version,
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
            agent_application=getattr(device, 'agent_application', None),
            device=device,
            code=device_code,
            action=DeviceAuthLog.ACTION_ACTIVATE,
            result=result,
            message=message,
            ip_address=_client_ip(request),
            device_info=device_info,
        )


@extend_schema_view(
    list=extend_schema(tags=['Wake Words']),
    retrieve=extend_schema(tags=['Wake Words']),
    create=extend_schema(tags=['Wake Words']),
    update=extend_schema(tags=['Wake Words']),
    partial_update=extend_schema(tags=['Wake Words']),
    destroy=extend_schema(tags=['Wake Words']),
)
class WakeWordViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = WakeWord.objects.prefetch_related('devices').all()
    serializer_class = WakeWordSerializer

    @staticmethod
    def _wake_word_devices_payload(wake_word: WakeWord) -> tuple[list[int], list[str]]:
        devices = list(wake_word.devices.order_by('id').values_list('id', 'code'))
        return [device_id for device_id, _ in devices], [code for _, code in devices]

    @staticmethod
    def _wake_word_target_devices(
        tenant_id: int | None,
        device_ids: list[int],
        device_codes: list[str],
    ) -> tuple[list[int], list[str]]:
        filters = Q()
        if device_ids:
            filters |= Q(id__in=device_ids)
        if device_codes:
            filters |= Q(code__in=device_codes)
        if not filters:
            return [], []

        devices = Device.objects.filter(filters, tenant_id=tenant_id).order_by('id')
        target_devices = [(device.id, device.code) for device in devices]
        return [device_id for device_id, _ in target_devices], [code for _, code in target_devices]

    @staticmethod
    def _publish_wake_word_changed(
        wake_word: WakeWord,
        action: str,
        *,
        device_ids: list[int] | None = None,
        device_codes: list[str] | None = None,
    ) -> None:
        if device_ids is None or device_codes is None:
            device_ids, device_codes = WakeWordViewSet._wake_word_devices_payload(wake_word)
        device_ids, device_codes = WakeWordViewSet._wake_word_target_devices(
            wake_word.tenant_id,
            device_ids,
            device_codes,
        )
        payload = {
            'type': 'device.wake_words.changed',
            'action': 'wakeWordsChanged',
            'operation': action,
            'resource': 'wakeWords',
            'tenantId': wake_word.tenant_id,
            'wakeWordId': wake_word.id,
            'text': wake_word.text,
            'deviceIds': device_ids,
            'deviceCodes': device_codes,
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': 'wakeWordsChanged',
            },
        }
        transaction.on_commit(lambda: publish_device_event_sync(payload))

    def perform_create(self, serializer):
        wake_word = serializer.save()
        self._publish_wake_word_changed(wake_word, 'create')

    def perform_update(self, serializer):
        old_device_ids, old_device_codes = self._wake_word_devices_payload(serializer.instance)
        wake_word = serializer.save()
        new_device_ids, new_device_codes = self._wake_word_devices_payload(wake_word)
        device_ids = sorted(set(old_device_ids) | set(new_device_ids))
        device_codes = sorted(set(old_device_codes) | set(new_device_codes))
        self._publish_wake_word_changed(
            wake_word,
            'update',
            device_ids=device_ids,
            device_codes=device_codes,
        )

    def perform_destroy(self, instance):
        device_ids, device_codes = self._wake_word_devices_payload(instance)
        tenant_id = instance.tenant_id
        wake_word_id = instance.id
        text = instance.text
        instance.delete()
        device_ids, device_codes = self._wake_word_target_devices(
            tenant_id,
            device_ids,
            device_codes,
        )
        payload = {
            'type': 'device.wake_words.changed',
            'action': 'wakeWordsChanged',
            'operation': 'delete',
            'resource': 'wakeWords',
            'tenantId': tenant_id,
            'wakeWordId': wake_word_id,
            'text': text,
            'deviceIds': device_ids,
            'deviceCodes': device_codes,
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': 'wakeWordsChanged',
            },
        }
        transaction.on_commit(lambda: publish_device_event_sync(payload))

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(text__icontains=keyword) | Q(encoded_text__icontains=keyword))
        status_filter = self.request.query_params.get('isActive', '').strip().lower()
        if status_filter == 'true':
            queryset = queryset.filter(is_active=True)
        if status_filter == 'false':
            queryset = queryset.filter(is_active=False)
        device_id = self.request.query_params.get('deviceId', '').strip()
        if device_id.isdigit():
            queryset = queryset.filter(devices__id=int(device_id))
        return queryset.distinct()


class DeviceRuntimeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_device_code(self, request) -> str:
        return str(
            request.headers.get('X-Device-Code')
            or request.data.get('deviceCode')
            or request.data.get('device_code')
            or request.query_params.get('deviceCode')
            or request.query_params.get('device_code')
            or ''
        ).strip()

    def validate_device(self, request, *, allow_expired: bool = False):
        try:
            return get_runtime_device(self.get_device_code(request), allow_expired=allow_expired), None
        except RuntimeDeviceError as exc:
            return None, Response(exc.as_payload(), status=exc.status_code)


class DeviceRuntimeConfigView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def get(self, request):
        device, error = self.validate_device(request, allow_expired=True)
        if error is not None:
            return error
        expiration_payload = {
            'authorizationExpired': device.is_expired,
            'expiresAt': serializers.DateTimeField().to_representation(device.expires_at),
        }
        if device.is_expired and device.is_software_trial:
            error = runtime_device_error('设备授权已过期', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_EXPIRED)
            return Response(
                {**error.as_payload(), **expiration_payload},
                status=error.status_code,
            )
        application = device.application
        agent_application = device.effective_agent_application
        if agent_application is None or not agent_application.runtime_config().get('is_active'):
            error = runtime_device_error('设备未绑定可用智能体', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_AGENT_UNBOUND)
            return Response(error.as_payload(), status=error.status_code)
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=application,
            agent_application=agent_application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_CONFIG,
            result=True,
            message='配置拉取成功',
            ip_address=_client_ip(request),
        )
        return Response(
            {
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
                **expiration_payload,
                **self._config_payload(device, request=request, include_resources=True),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _config_payload(device: Device, request=None, *, include_resources: bool = False, include_scrolling_texts: bool = False):
        application = device.application
        agent_application = device.effective_agent_application
        payload = {
            'device': DeviceSerializer(device, context={'request': request}).data,
            'application': (
                {
                    'id': application.id,
                    'name': application.name,
                    'code': application.code,
                }
                if application is not None
                else None
            ),
            'agentApplication': DeviceActivationView._agent_application_payload(agent_application),
            **DeviceRuntimeConfigView._wake_words_payload(device),
        }
        if include_resources:
            payload['resources'] = DeviceRuntimeConfigView._resources_payload(device, request)
        else:
            payload['voiceConfiguration'] = DeviceRuntimeConfigView._voice_configuration_payload(device)
        if include_scrolling_texts:
            payload['scrollingTexts'] = DeviceRuntimeConfigView._scrolling_texts_payload(device)
        return payload

    @staticmethod
    def _voice_configuration_payload(device: Device):
        voice = DeviceRuntimeConfigView._device_voice(device)
        return {
            'voiceTones': [
                DeviceRuntimeConfigView._voice_payload(voice, config=public_device_tts_voice_config(device, getattr(voice, 'provider', None)))
            ] if voice is not None else [],
        }

    @staticmethod
    def _device_voice(device: Device):
        voice = getattr(device, 'tts_voice', None)
        if voice is None:
            return tts_services.get_effective_tts_voice_for_tenant(device.tenant)
        provider = getattr(voice, 'provider', None)
        if not voice.is_active or not voice.is_visible or provider is None or not provider.is_active:
            return None
        return voice

    @staticmethod
    def _voice_payload(voice, request=None, config=None):
        icon_url = voice.avatar_path
        if request is not None and icon_url.startswith('/'):
            icon_url = request.build_absolute_uri(icon_url)
        return {
            'id': voice.id,
            'name': voice.display_name,
            'voiceCode': voice.voice_code,
            'audioUrl': '',
            'iconUrl': icon_url,
            **(config or {}),
        }

    @staticmethod
    def _scrolling_texts_payload(device: Device):
        tenant = device.tenant
        if tenant is None:
            return []
        scrolling_texts = (
            ScrollingText.objects.filter(tenant=tenant, is_active=True)
            .prefetch_related('items')
            .order_by('-updated_at', '-id')
        )
        return [
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
            for item in scrolling_texts
        ]

    @staticmethod
    def _resources_payload(device: Device, request):
        def file_url(file_field):
            if not file_field:
                return ''
            return request.build_absolute_uri(file_field.url)

        tenant = device.tenant
        application = device.application
        if tenant is None:
            return {
                'images': [],
                'videos': [],
                'scrollingTexts': [],
                'voiceTones': [],
                'models': [],
                'commandGroups': [],
            }

        images = Resource.objects.filter(tenant=tenant, resource_type=Resource.TYPE_IMAGE).order_by('-updated_at', '-id')
        videos = Resource.objects.filter(tenant=tenant, resource_type=Resource.TYPE_VIDEO).order_by('-updated_at', '-id')
        models = ModelAsset.objects.filter(tenant=tenant, is_visible=True).order_by('-updated_at', '-id')
        scrolling_texts = ScrollingText.objects.filter(tenant=tenant, is_active=True).prefetch_related('items').order_by('-updated_at', '-id')
        application_is_active = application is not None and application.is_active
        voice = DeviceRuntimeConfigView._device_voice(device)

        def resource_url(item):
            if item.cloud_url:
                return item.cloud_url
            if item.object_key:
                return build_public_object_url(item.object_key, backend=item.storage_backend)
            return file_url(item.file)

        return {
            'images': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': resource_url(item),
                    'category': item.category,
                }
                for item in images
            ],
            'videos': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': resource_url(item),
                    'category': item.category,
                }
                for item in videos
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
                for item in scrolling_texts
            ],
            'voiceTones': [
                DeviceRuntimeConfigView._voice_payload(
                    voice,
                    request,
                    public_device_tts_voice_config(device, getattr(voice, 'provider', None)),
                )
                for voice in ([voice] if voice is not None else [])
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
                for item in models
            ],
            'commandGroups': [
                {
                    'id': item.id,
                    'name': item.name,
                    'groupType': item.group_type,
                }
                for item in (
                    application.command_groups.filter(is_active=True)
                    if application_is_active
                    else []
                )
            ],
        }


    @staticmethod
    def _wake_words_payload(device: Device):
        wake_words = device.wake_words.filter(is_active=True).order_by('text', 'id')
        items = [
            {
                'id': item.id,
                'text': item.text,
                'encodedText': item.encoded_text,
                'keywordLine': item.keyword_line,
                'boost': float(item.boost),
                'threshold': float(item.threshold),
            }
            for item in wake_words
        ]
        return {
            'wakeWords': items,
            'wakeWordLines': [item['keywordLine'] for item in items],
        }


class DeviceRuntimeResourcesView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def post(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error

        application = device.application
        agent_application = device.effective_agent_application
        resource_type = str(request.data.get('resourceType') or request.data.get('resource_type') or 'application').strip()
        payload = DeviceRuntimeConfigView._resources_payload(device, request)
        resource_map = {
            'application': None,
            'voiceTones': payload['voiceTones'],
            'images': payload['images'],
            'scrollingTexts': payload['scrollingTexts'],
            'models': payload['models'],
            'videos': payload['videos'],
        }
        if resource_type not in resource_map:
            return Response(
                {'resourceType': '支持 application、voiceTones、images、scrollingTexts、models、videos'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_payload = {
            'requestId': get_request_id(request),
            'traceId': get_trace_id(request),
            'resourceType': resource_type,
            'items': [] if resource_type == 'application' else resource_map[resource_type],
        }
        if resource_type == 'application':
            application_payload = self._application_payload(application)
            agent_payload = self._agent_application_payload(agent_application)
            response_payload['device'] = DeviceSerializer(device, context={'request': request}).data
            response_payload['application'] = application_payload
            response_payload['agentApplication'] = agent_payload
            response_payload['resources'] = payload
        return Response(response_payload, status=status.HTTP_200_OK)

    @staticmethod
    def _application_payload(application):
        if application is None:
            return None
        return {
            'id': application.id,
            'name': application.name,
            'code': application.code,
            'description': application.description,
            'isActive': application.is_active,
        }

    @staticmethod
    def _agent_application_payload(agent_application):
        if agent_application is None:
            return None
        config = agent_application.runtime_config()
        return {
            **DeviceActivationView._agent_application_payload(agent_application),
            'description': config.get('description') or '',
            'systemPrompt': config.get('system_prompt') or '',
            'temperature': config.get('temperature'),
            'maxTokens': config.get('max_tokens'),
            'maxTokensUnlimited': config.get('max_tokens_unlimited'),
            'openingMessageEnabled': config.get('opening_message_enabled'),
            'openingMessage': config.get('opening_message') or '',
            'suggestedQuestions': config.get('suggested_questions') or [],
            'followUpSuggestedQuestionsEnabled': config.get('follow_up_suggested_questions_enabled', False),
            'voiceInputEnabled': config.get('voice_input_enabled'),
            'replyPlaybackEnabled': config.get('reply_playback_enabled'),
            'ttsFilterPunctuation': config.get('tts_filter_punctuation') or '',
            'ttsFilterEmoji': config.get('tts_filter_emoji'),
            'ttsFilterExcludePatterns': config.get('tts_filter_exclude_patterns') or [],
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
            agent_application=device.agent_application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_HEARTBEAT,
            result=True,
            message='心跳成功',
            ip_address=_client_ip(request),
            device_info=request.data.get('deviceInfo') or request.data.get('device_info') or {},
        )
        return Response(
            {
                'status': 'success',
                'message': '心跳成功',
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
            },
            status=status.HTTP_200_OK,
        )


class DeviceVoiceChatView(DeviceRuntimeView):
    parser_classes = [MultiPartParser, JSONParser]

    @extend_schema(tags=['Device Runtime'])
    def post(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        try:
            validate_runtime_application_active(device)
        except RuntimeDeviceError as exc:
            return Response(exc.as_payload(), status=exc.status_code)
        if device.effective_agent_application is None or not device.effective_agent_application.runtime_config().get('is_active'):
            error = runtime_device_error('设备未绑定可用智能体', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_AGENT_UNBOUND)
            return Response(error.as_payload(), status=error.status_code)

        pipeline_context = {
            'requestId': get_request_id(request),
            'traceId': get_trace_id(request),
            'deviceCode': device.code,
            'sessionId': None,
        }
        request_input = {
            key: request.data.get(key)
            for key in request.data
            if key != 'audio'
        }
        audio_file = request.FILES.get('audio')
        if audio_file is not None:
            request_input['audio'] = {
                'name': audio_file.name,
                'contentType': audio_file.content_type,
                'size': audio_file.size,
            }
        _log_http_voice_pipeline('http.request', pipeline_context, {'request': request_input})

        question_text = self._request_question_text(request)
        if not question_text:
            if audio_file is None:
                return Response({'message': '请上传语音或输入文本'}, status=status.HTTP_400_BAD_REQUEST)
            audio_format = str(request.data.get('format') or 'pcm').strip().lower()
            if audio_format != 'pcm':
                return Response({'message': '语音问答接口暂只支持 16k PCM 音频'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
            sample_rate, sample_error = self._request_sample_rate(request)
            if sample_error is not None:
                return sample_error
            try:
                pcm = audio_file.read()
                _log_http_voice_pipeline(
                    'asr.request',
                    pipeline_context,
                    {
                        'format': audio_format,
                        'sampleRate': sample_rate,
                        'audio': {'name': audio_file.name, 'byteLength': len(pcm)},
                    },
                )
                question_text = asr_services.transcribe_pcm_audio(
                    pcm=pcm,
                    sample_rate=sample_rate,
                    tenant_id=device.tenant_id,
                )
            except Exception as exc:
                return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)
            _log_http_voice_pipeline('asr.response', pipeline_context, {'questionText': question_text})
            if not question_text:
                return Response({'message': 'ASR 没有识别出有效内容'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            _log_http_voice_pipeline('asr.bypassed', pipeline_context, {'questionText': question_text})

        runtime_config = device.effective_agent_application.runtime_config() if device.effective_agent_application is not None else {}
        is_standard_voice_backend = runtime_config.get('runtime_backend_type') != RUNTIME_BACKEND_THIRD_PARTY_CHATBOT

        # --- session management ---------------------------------------------------
        # The backend owns the voice-chat session id.  The first request from the
        # device intentionally omits sessionId; generate it before answering so
        # the first turn is stored under the same id that is returned to Android.
        incoming_session_id = str(request.data.get('sessionId') or '').strip()
        session_id = incoming_session_id or str(uuid.uuid4())
        pipeline_context['sessionId'] = session_id
        if is_standard_voice_backend:
            logger.info(
                '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：session_id 会话ID：%s',
                question_text,
                session_id,
            )

        try:
            answer_text, answer_blocks, answer_source = self._generate_answer(
                device, question_text, session_id=session_id, request=request, pipeline_context=pipeline_context,
            )
        except Exception as exc:
            return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)

        # Persist conversation turns so the next request can load history.
        if is_standard_voice_backend:
            logger.info(
                '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：session_id 会话ID：%s',
                question_text,
                session_id,
            )
        session_store.append_turn(device.code, session_id, 'user', question_text)
        session_store.append_turn(device.code, session_id, 'assistant', answer_text)
        if is_standard_voice_backend:
            logger.info(
                '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：session_id 会话ID：%s',
                question_text,
                session_id,
            )

        try:
            runtime_agent = device.effective_agent_application
            runtime_model_name = ''
            runtime_config = runtime_agent.runtime_config() if runtime_agent is not None else {}
            if runtime_config.get('runtime_backend_type') == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
                runtime_chatbot_id = runtime_config.get('third_party_chatbot_id')
                runtime_chatbot = (
                    ThirdPartyChatbotApplication.objects.filter(id=runtime_chatbot_id).first()
                    if runtime_chatbot_id
                    else None
                )
                runtime_model_name = runtime_chatbot.name if runtime_chatbot is not None else ''
                if not runtime_model_name and runtime_agent and runtime_agent.third_party_chatbot:
                    runtime_model_name = runtime_agent.third_party_chatbot.name
            else:
                runtime_model_id = runtime_config.get('llm_model_id')
                runtime_model = LLMModel.objects.filter(id=runtime_model_id).first() if runtime_model_id else None
                runtime_model_name = runtime_model.name if runtime_model is not None else ''
                if not runtime_model_name and runtime_agent and runtime_agent.llm_model:
                    runtime_model_name = runtime_agent.llm_model.name
            record_device_chat_log(
                device,
                question_text,
                answer_text,
                source=DeviceChatLog.SOURCE_HTTP,
                request_id=pipeline_context['requestId'],
                trace_id=pipeline_context['traceId'],
                model_name=runtime_model_name,
                runtime_session_id=session_id,
                answer_blocks=answer_blocks,
            )
        except Exception:
            logger.exception('device.voice_chat.log_failed device_code=%s', device.code)

        if is_standard_voice_backend:
            logger.info(
                '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：payload.sessionId 会话ID：%s',
                question_text,
                session_id,
            )
        payload = {
            'sessionId': session_id,
            'requestId': pipeline_context['requestId'],
            'traceId': pipeline_context['traceId'],
            'deviceCode': device.code,
            'questionText': question_text,
            'answerText': answer_text,
            'answerBlocks': answer_blocks,
            'followUpSuggestedQuestions': [],
            'audioBase64': None,
            'audioContentType': 'audio/wav',
        }
        try:
            runtime_agent = device.effective_agent_application
            runtime_config = runtime_agent.runtime_config() if runtime_agent is not None else {}
            if (
                answer_source == 'platform_llm'
                and runtime_agent is not None
                and bool(runtime_config.get('follow_up_suggested_questions_enabled'))
                and answer_text
            ):
                from apps.ai_models.services.follow_up_suggested_questions import (
                    generate_follow_up_suggested_questions,
                )

                model = None
                runtime_model_id = runtime_config.get('llm_model_id')
                if runtime_model_id:
                    model = LLMModel.objects.filter(id=runtime_model_id).select_related('provider').first()
                if model is None and runtime_agent.llm_model_id:
                    model = LLMModel.objects.filter(id=runtime_agent.llm_model_id).select_related('provider').first()
                history = session_store.get_history(device.code, session_id) if session_id else []
                payload['followUpSuggestedQuestions'] = generate_follow_up_suggested_questions(
                    model=model,
                    history_messages=history,
                    latest_answer=answer_text,
                    enabled=True,
                )
        except Exception:
            logger.exception('device.voice_chat.follow_up_failed device_code=%s', device.code)
            payload['followUpSuggestedQuestions'] = []
        try:
            payload['audioBase64'] = self._synthesize_answer_audio(device, answer_text, pipeline_context=pipeline_context)
        except Exception as exc:
            payload['ttsError'] = str(exc)[:200]
            _log_http_voice_pipeline('tts.error', pipeline_context, {'message': payload['ttsError']})
        _log_http_voice_pipeline('http.response', pipeline_context, payload)
        return Response(payload, status=status.HTTP_200_OK)

    @staticmethod
    def _request_question_text(request) -> str:
        return str(
            request.data.get('text')
            or request.data.get('questionText')
            or request.data.get('question')
            or ''
        ).strip()

    @staticmethod
    def _request_sample_rate(request):
        raw_sample_rate = request.data.get('sampleRate') or request.data.get('sample_rate') or 16000
        try:
            sample_rate = int(raw_sample_rate)
        except (TypeError, ValueError):
            return None, Response({'message': 'sampleRate 必须是整数'}, status=status.HTTP_400_BAD_REQUEST)
        if sample_rate <= 0 or sample_rate > 48000:
            return None, Response({'message': 'sampleRate 超出支持范围'}, status=status.HTTP_400_BAD_REQUEST)
        return sample_rate, None

    @staticmethod
    def _generate_answer(
        device: Device,
        question_text: str,
        *,
        session_id: str | None = None,
        request=None,
        pipeline_context: dict[str, str | None] | None = None,
    ) -> tuple[str, list[dict], str]:
        agent_application = device.effective_agent_application
        annotation = DeviceVoiceChatView._find_annotation(agent_application, question_text)
        if annotation is not None:
            now = timezone.now()
            annotation_id = annotation.get('id') if isinstance(annotation, dict) else annotation.id
            AgentAnnotation.objects.filter(id=annotation_id).update(
                hit_count=F('hit_count') + 1,
                last_hit_at=now,
            )
            if isinstance(annotation, dict):
                blocks = annotation.get('answerBlocks') or text_to_blocks(annotation.get('answer') or '')
                answer_text = blocks_to_text(blocks)
                if pipeline_context is not None:
                    _log_http_voice_pipeline('llm.request', pipeline_context, {'backend': 'annotation', 'questionText': question_text, 'annotationId': annotation_id})
                    _log_http_voice_pipeline('llm.response', pipeline_context, {'answerText': answer_text, 'answerBlocks': blocks})
                return answer_text, serialize_published_annotation_blocks(annotation, tenant=agent_application.tenant, request=request), 'annotation'
            blocks = annotation.answer_blocks or text_to_blocks(annotation.answer)
            answer_text = blocks_to_text(blocks)
            if pipeline_context is not None:
                _log_http_voice_pipeline('llm.request', pipeline_context, {'backend': 'annotation', 'questionText': question_text, 'annotationId': annotation_id})
                _log_http_voice_pipeline('llm.response', pipeline_context, {'answerText': answer_text, 'answerBlocks': blocks})
            return answer_text, serialize_reply_blocks(blocks, tenant=agent_application.tenant, request=request), 'annotation'

        runtime_config = agent_application.runtime_config() if agent_application is not None else {}
        if runtime_config.get('runtime_backend_type') == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
            chatbot = None
            runtime_chatbot_id = runtime_config.get('third_party_chatbot_id')
            if runtime_chatbot_id:
                chatbot = ThirdPartyChatbotApplication.objects.select_related('provider').filter(id=runtime_chatbot_id).first()
            if chatbot is None and agent_application is not None:
                chatbot = agent_application.third_party_chatbot
            if not third_party_chatbots.is_chatbot_effective_for_tenant(device.tenant, chatbot):
                raise RuntimeError('请先为设备绑定智能体配置可用第三方会话机器人')
            conversation = DeviceVoiceChatView._resolve_third_party_conversation(
                device,
                agent_application,
                chatbot,
                runtime_config,
                session_id,
            )
            if pipeline_context is not None:
                _log_http_voice_pipeline(
                    'llm.request',
                    pipeline_context,
                    {
                        'backend': 'third_party_chatbot',
                        'chatbot': {'id': chatbot.id, 'name': chatbot.name, 'externalApplicationId': chatbot.external_application_id},
                        'runtimeConfig': runtime_config,
                        'questionText': question_text,
                        'conversationId': conversation.id if conversation is not None else None,
                    },
                )
            answer_text = third_party_chatbots.send_chatbot_message(chatbot, question_text, conversation=conversation)
            if pipeline_context is not None:
                _log_http_voice_pipeline('llm.response', pipeline_context, {'answerText': answer_text})
            return answer_text, serialize_reply_blocks(text_to_blocks(answer_text), tenant=device.tenant), 'third_party'

        model = None
        runtime_model_id = runtime_config.get('llm_model_id')
        if runtime_model_id:
            model = LLMModel.objects.select_related('provider').filter(id=runtime_model_id).first()
        if model is None:
            model = agent_application.llm_model if agent_application is not None else None
        if model is None:
            settings = llm_services.get_tenant_llm_settings(device.tenant)
            model = settings.default_model if settings is not None else None
        if not llm_services.is_llm_model_effective_for_tenant(device.tenant, model):
            raise RuntimeError('请先为设备绑定智能体配置可用 LLM 模型')

        system_prompt = (
            str(runtime_config.get('system_prompt') or '').strip()
            if agent_application is not None and str(runtime_config.get('system_prompt') or '').strip()
            else '你是数字人设备的中文语音问答助手。回答要自然、简洁，适合直接转成语音播报。'
        )
        messages = [{'role': 'system', 'content': system_prompt}]
        # Load conversation history from Redis when a sessionId is provided.
        if session_id:
            history = session_store.get_history(device.code, session_id)
            logger.info(
                '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：_generate_answer.session_id 会话ID：%s',
                question_text,
                session_id,
            )
            messages.extend(history)
        media_blocks: list[dict] = []
        if agent_application is not None:
            from apps.ai_models.services.agent_knowledge import retrieve_knowledge_context_with_media

            knowledge_context, media_blocks = retrieve_knowledge_context_with_media(
                agent_application,
                question_text,
                knowledge_document_ids=runtime_config.get('knowledge_document_ids') or [],
                knowledge_base_ids=runtime_config.get('knowledge_base_ids') or [],
            )
            if knowledge_context:
                messages.append({'role': 'system', 'content': knowledge_context})
        messages.append({'role': 'user', 'content': question_text})
        temperature = runtime_config.get('temperature', 0.7) if agent_application is not None else 0.7
        max_tokens = None if agent_application is not None and runtime_config.get('max_tokens_unlimited') else (runtime_config.get('max_tokens', 1000) if agent_application is not None else 1000)
        if pipeline_context is not None:
            _log_http_voice_pipeline(
                'llm.request',
                pipeline_context,
                {
                    'backend': 'platform_llm',
                    'model': {'id': model.id, 'name': model.name, 'provider': model.provider.name},
                    'messages': messages,
                    'temperature': temperature,
                    'maxTokens': max_tokens,
                },
            )
        answer_text = llm_services.run_llm_chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not answer_text:
            raise RuntimeError('LLM 没有返回有效回复')
        if pipeline_context is not None:
            _log_http_voice_pipeline('llm.response', pipeline_context, {'answerText': answer_text})
        return answer_text, serialize_reply_blocks(
            [*text_to_blocks(answer_text), *media_blocks],
            tenant=device.tenant,
            request=request,
        ), 'platform_llm'

    @staticmethod
    def _resolve_third_party_conversation(device: Device, agent_application, chatbot, runtime_config: dict, session_id: str | None):
        if not session_id:
            return None
        conversation = (
            ChatConversation.objects
            .select_related('third_party_chatbot__provider', 'application')
            .filter(
                tenant=device.tenant,
                application=agent_application,
                external_session__runtimeSessionId=session_id,
            )
            .first()
        )
        if conversation is not None:
            return conversation

        user = DeviceVoiceChatView._runtime_conversation_user(agent_application, device.tenant)
        return ChatConversation.objects.create(
            title=f'{runtime_config.get("name") or agent_application.name} 语音会话',
            user=user,
            runtime_backend_type=RUNTIME_BACKEND_THIRD_PARTY_CHATBOT,
            third_party_chatbot=chatbot,
            external_session={'runtimeSessionId': session_id},
            summary='',
            system_prompt=runtime_config.get('system_prompt') or '',
            temperature=runtime_config.get('temperature', 0.7),
            max_tokens=runtime_config.get('max_tokens', 1000),
            max_tokens_unlimited=runtime_config.get('max_tokens_unlimited', False),
            application=agent_application,
            tenant=device.tenant,
        )

    @staticmethod
    def _runtime_conversation_user(agent_application, tenant):
        if getattr(agent_application, 'created_by_id', None):
            return agent_application.created_by

        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(membership__tenant=tenant).order_by('-membership__is_tenant_admin', 'id').first()
        if user is not None:
            return user

        username = f'runtime_tenant_{tenant.id}'
        user, _ = User.objects.get_or_create(username=username, defaults={'is_active': False})
        return user

    @staticmethod
    def _find_annotation(agent_application, question_text: str):
        if agent_application is None:
            return None
        if agent_application.published_at:
            return find_matching_published_annotation(agent_application.published_annotations, question_text)
        return find_matching_annotation(agent_application.annotations, question_text)

    @staticmethod
    def _synthesize_answer_audio(device: Device, answer_text: str, *, pipeline_context: dict[str, str | None] | None = None) -> str:
        provider = tts_services.get_aliyun_tts_provider()
        config = tts_services.get_effective_tts_config(provider)
        device_voice = getattr(device, 'tts_voice', None)
        if device_voice is not None:
            voice = device_voice if device_voice.provider_id == provider.id and tts_services.is_voice_available(device_voice) else None
        else:
            voice = tts_services.get_effective_tts_voice_for_tenant(device.tenant, provider)
        if voice is None:
            raise RuntimeError('请先配置默认音色')
        session_config = device_tts_session_config(device, provider)
        if pipeline_context is not None:
            _log_http_voice_pipeline(
                'tts.request',
                pipeline_context,
                {
                    'text': answer_text,
                    'providerCode': provider.code,
                    'model': config.model,
                    'voice': {'id': voice.id, 'voiceCode': voice.voice_code},
                    'sessionConfig': session_config,
                },
            )
        pcm = tts_services.synthesize_tts_pcm(text=answer_text, voice=voice, config=config, session_config=session_config)
        wav = tts_services.pcm_to_wav(pcm, sample_rate=session_config.get('sample_rate') or config.sample_rate)
        audio_base64 = base64.b64encode(wav).decode('ascii')
        if pipeline_context is not None:
            _log_http_voice_pipeline(
                'tts.response',
                pipeline_context,
                {'pcmByteLength': len(pcm), 'wavByteLength': len(wav), 'audioBase64Length': len(audio_base64)},
            )
        return audio_base64
