from pathlib import Path

from django.db import transaction
from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view

from apps.accounts.permissions import (
    CanCreateCommandGroups,
    CanCreateControlCommands,
    CanCreateImageResources,
    CanCreateModels,
    CanCreateScrollingTexts,
    CanCreateTaskCommands,
    CanCreateVideoResources,
    CanCreateVoiceTones,
    CanDeleteCommandGroups,
    CanDeleteControlCommands,
    CanDeleteImageResources,
    CanDeleteModels,
    CanDeleteScrollingTexts,
    CanDeleteTaskCommands,
    CanDeleteVideoResources,
    CanDeleteVoiceTones,
    CanUpdateCommandGroups,
    CanUpdateControlCommands,
    CanUpdateImageResources,
    CanUpdateModels,
    CanUpdateScrollingTexts,
    CanUpdateTaskCommands,
    CanUpdateVideoResources,
    CanUpdateVoiceTones,
    CanViewCommandGroups,
    CanViewControlCommands,
    CanViewImageResources,
    CanViewModels,
    CanViewScrollingTexts,
    CanViewTaskCommands,
    CanViewVideoResources,
    CanViewVoiceTones,
    IsAdminRole,
    IsSuperUser,
)
from config.business_cache import CachedBusinessResponseMixin
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.models import Tenant
from apps.tenants.services import get_request_tenant, resolve_member_or_public_tenant, scope_queryset_member_or_public
from apps.accounts.authentication import TenantAwareJWTAuthentication

from apps.devices.realtime import publish_device_event_sync
from .models import CommandGroup, ControlCommand, ControlCommandRecognitionPolicy, MinioConfig, ModelAsset, Resource, ScrollingText, ScrollingTextItem, TaskCommand, TaskCommandStep, TenantVideoQuota, VoiceTone
from .serializers import (
    CommandGroupSerializer,
    ControlCommandSerializer,
    ControlCommandRecognitionPolicySerializer,
    ImageResourceBulkDeleteSerializer,
    ModelAssetSerializer,
    MinioConfigSerializer,
    TenantVideoQuotaSerializer,
    ResourceSerializer,
    ScrollingTextSerializer,
    TaskCommandSerializer,
    VoiceToneSerializer,
    build_task_command_list,
    build_task_step_runtime_data,
)
from .services.minio_client import (
    MinioConfigError,
    delete_object,
    get_minio_settings,
    get_resource_upload_config,
    get_video_upload_config,
    presign_resource_put_url,
    presign_video_put_url,
)
from .services.image_hashes import DuplicateImageError, find_duplicate_image, normalize_sha256
from .tasks import enqueue_command_change_notification, enqueue_command_notification


class PermissionMappedModelViewSet(viewsets.ModelViewSet):
    permission_map = {}

    def get_permissions(self):
        permission_classes = self.permission_map.get(self.action, self.permission_map.get('list', []))
        return [permission() for permission in permission_classes]


def get_business_write_tenant(request):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_superuser:
        raw = request.query_params.get('tenant')
        if raw and raw.strip().isdigit():
            return Tenant.objects.filter(id=int(raw), is_active=True).first()
        return None
    return get_request_tenant(request)


@extend_schema(tags=['Commands'])
class ControlCommandRecognitionPolicyView(APIView):
    def get_permissions(self):
        permission = CanUpdateControlCommands if self.request.method in {'PATCH', 'DELETE'} else CanViewControlCommands
        return [permission()]

    @staticmethod
    def _policy_or_error(request):
        tenant = get_business_write_tenant(request)
        if tenant is None:
            return None, Response({'message': '当前请求缺少公司范围'}, status=status.HTTP_400_BAD_REQUEST)
        policy, _ = ControlCommandRecognitionPolicy.objects.get_or_create(tenant=tenant)
        return policy, None

    def get(self, request):
        policy, error_response = self._policy_or_error(request)
        if error_response is not None:
            return error_response
        return Response(ControlCommandRecognitionPolicySerializer(policy).data)

    def patch(self, request):
        policy, error_response = self._policy_or_error(request)
        if error_response is not None:
            return error_response
        serializer = ControlCommandRecognitionPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request):
        policy, error_response = self._policy_or_error(request)
        if error_response is not None:
            return error_response
        policy.direct_execution_threshold = ControlCommandRecognitionPolicy.DIRECT_EXECUTION_THRESHOLD_DEFAULT
        policy.llm_confirmation_threshold = ControlCommandRecognitionPolicy.LLM_CONFIRMATION_THRESHOLD_DEFAULT
        policy.save(update_fields=['direct_execution_threshold', 'llm_confirmation_threshold', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CanCreateAnyResource:
    message = '当前账号缺少资源创建权限'

    def has_permission(self, request, view):
        return CanCreateImageResources().has_permission(request, view) or CanCreateVideoResources().has_permission(request, view)


class BaseResourceViewSet(CachedBusinessResponseMixin, TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = ResourceSerializer
    lookup_field = 'pk'
    resource_type = ''
    business_cache_namespace = 'resources'

    def get_queryset(self):
        queryset = Resource.objects.filter(resource_type=self.resource_type).order_by('-updated_at', '-id')
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        if self.resource_type == Resource.TYPE_IMAGE:
            is_digital_human_background = (
                self.request.query_params.get('isDigitalHumanBackground')
                or self.request.query_params.get('is_digital_human_background')
                or ''
            ).strip().lower()
            if is_digital_human_background in {'true', 'false'}:
                queryset = queryset.filter(is_digital_human_background=is_digital_human_background == 'true')
        return self.apply_tenant_scope(queryset)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['resource_type'] = self.resource_type
        context['object_key_tenant'] = get_business_write_tenant(self.request)
        return context

    def tenant_create_kwargs(self) -> dict:
        tenant = get_business_write_tenant(self.request)
        return {'tenant': tenant} if tenant is not None else {}

    def perform_destroy(self, instance):
        reference_count = self._agent_annotation_reference_count(instance)
        if reference_count:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'message': f'该资源被 {reference_count} 个标注回复引用，不能删除'})
        object_key = (instance.object_key or '').strip()
        storage_backend = instance.storage_backend
        super().perform_destroy(instance)
        if object_key:
            delete_object(object_key, backend=storage_backend)

    @staticmethod
    def _agent_annotation_reference_count(resource: Resource) -> int:
        from apps.ai_models.models import AgentAnnotation, AgentApplication

        def blocks_reference_resource(blocks) -> bool:
            if not isinstance(blocks, list):
                return False
            return any(isinstance(block, dict) and block.get('resourceId') == resource.id for block in blocks)

        count = 0
        for annotation in AgentAnnotation.objects.filter(tenant=resource.tenant).only('answer_blocks'):
            if blocks_reference_resource(annotation.answer_blocks):
                count += 1
        for application in AgentApplication.objects.filter(tenant=resource.tenant).only('published_annotations'):
            for annotation in application.published_annotations or []:
                if isinstance(annotation, dict) and blocks_reference_resource(annotation.get('answerBlocks')):
                    count += 1
        return count


@extend_schema_view(
    list=extend_schema(tags=['Resources']),
    retrieve=extend_schema(tags=['Resources']),
    create=extend_schema(tags=['Resources']),
    update=extend_schema(tags=['Resources']),
    partial_update=extend_schema(tags=['Resources']),
    destroy=extend_schema(tags=['Resources']),
)
class ImageResourceViewSet(BaseResourceViewSet):
    resource_type = Resource.TYPE_IMAGE
    permission_map = {
        'list': [CanViewImageResources],
        'retrieve': [CanViewImageResources],
        'create': [CanCreateImageResources],
        'update': [CanUpdateImageResources],
        'partial_update': [CanUpdateImageResources],
        'destroy': [CanDeleteImageResources],
        'bulk': [CanCreateImageResources],
        'bulk_delete': [CanDeleteImageResources],
    }

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request):
        files = request.FILES.getlist('files')
        if not files:
            return Response({'files': '请至少选择一个图片文件'}, status=status.HTTP_400_BAD_REQUEST)

        category = request.data.get('category') or Resource.CATEGORY_UNCATEGORIZED
        description = str(request.data.get('description') or '').strip()
        is_digital_human_background = str(
            request.data.get('isDigitalHumanBackground') or request.data.get('is_digital_human_background') or ''
        ).strip().lower() == 'true'

        created_resources = []
        duplicates = []
        for uploaded_file in files:
            name = Path(uploaded_file.name).stem or uploaded_file.name
            serializer = self.get_serializer(
                data={
                    'name': name,
                    'category': category,
                    'description': description,
                    'file': uploaded_file,
                    'isDigitalHumanBackground': is_digital_human_background,
                }
            )
            try:
                serializer.is_valid(raise_exception=True)
                created_resources.append(serializer.save(**self.tenant_create_kwargs()))
            except DuplicateImageError:
                duplicates.append({'fileName': uploaded_file.name, 'reason': '该图片已存在'})

        if created_resources:
            self.clear_cached_business_responses()
        response_serializer = self.get_serializer(created_resources, many=True)
        response_status = status.HTTP_201_CREATED if created_resources else status.HTTP_200_OK
        return Response(
            {'created': response_serializer.data, 'duplicates': duplicates},
            status=response_status,
        )

    @bulk.mapping.delete
    def bulk_delete(self, request):
        serializer = ImageResourceBulkDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data['ids']
        resources = {resource.id: resource for resource in self.get_queryset().filter(id__in=ids)}
        deleted_ids = []
        failures = []

        for resource_id in ids:
            resource = resources.get(resource_id)
            if resource is None:
                failures.append(
                    {
                        'id': resource_id,
                        'name': '',
                        'reason': '图片不存在或无权访问',
                    }
                )
                continue

            try:
                self.perform_destroy(resource)
            except ValidationError as exc:
                detail = exc.detail.get('message') if isinstance(exc.detail, dict) else exc.detail
                if isinstance(detail, (list, tuple)):
                    detail = detail[0] if detail else ''
                failures.append(
                    {
                        'id': resource_id,
                        'name': resource.name,
                        'reason': str(detail or '图片无法删除'),
                    }
                )
                continue

            deleted_ids.append(resource_id)

        return Response({'deletedIds': deleted_ids, 'failures': failures})


@extend_schema_view(
    list=extend_schema(tags=['Resources']),
    retrieve=extend_schema(tags=['Resources']),
    create=extend_schema(tags=['Resources']),
    update=extend_schema(tags=['Resources']),
    partial_update=extend_schema(tags=['Resources']),
    destroy=extend_schema(tags=['Resources']),
)
class VideoResourceViewSet(BaseResourceViewSet):
    resource_type = Resource.TYPE_VIDEO
    permission_map = {
        'list': [CanViewVideoResources],
        'retrieve': [CanViewVideoResources],
        'create': [CanCreateVideoResources],
        'update': [CanUpdateVideoResources],
        'partial_update': [CanUpdateVideoResources],
        'destroy': [CanDeleteVideoResources],
    }

class VideoUploadConfigView(APIView):
    permission_classes = [CanCreateVideoResources]

    def get(self, request):
        return Response(get_video_upload_config(get_business_write_tenant(request)))


class ResourceUploadConfigView(APIView):
    permission_classes = [CanCreateAnyResource]

    def get(self, request):
        return Response(get_resource_upload_config(get_business_write_tenant(request)))


class ResourceUploadPresignView(APIView):
    def get_permissions(self):
        data = self.request.data if isinstance(self.request.data, dict) else {}
        resource_type = str(data.get('resourceType') or data.get('resource_type') or '').strip()
        permission = CanCreateImageResources if resource_type == Resource.TYPE_IMAGE else CanCreateVideoResources
        return [permission()]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        resource_type = str(data.get('resourceType') or data.get('resource_type') or '').strip()
        filename = str(data.get('filename') or '').strip()
        content_type = str(data.get('contentType') or data.get('content_type') or '').strip()
        try:
            file_size = int(data.get('fileSize') or data.get('file_size') or 0)
        except (TypeError, ValueError):
            file_size = 0

        if resource_type not in {Resource.TYPE_IMAGE, Resource.TYPE_VIDEO}:
            return Response({'resourceType': 'resourceType 必须是 image 或 video'}, status=status.HTTP_400_BAD_REQUEST)
        if not filename:
            return Response({'filename': 'filename 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if file_size <= 0:
            return Response({'fileSize': 'fileSize 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_business_write_tenant(request)
        if resource_type == Resource.TYPE_IMAGE:
            try:
                content_hash = normalize_sha256(data.get('contentHash') or data.get('content_hash'))
            except ValueError as exc:
                return Response({'contentHash': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            duplicate = find_duplicate_image(tenant=tenant, content_hash=content_hash)
            if duplicate is not None:
                raise DuplicateImageError(duplicate)
        try:
            return Response(
                presign_resource_put_url(
                    resource_type=resource_type,
                    filename=filename,
                    content_type=content_type,
                    file_size=file_size,
                    tenant=tenant,
                )
            )
        except MinioConfigError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class VideoUploadPresignView(APIView):
    permission_classes = [CanCreateVideoResources]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        filename = str(data.get('filename') or '').strip()
        content_type = str(data.get('contentType') or data.get('content_type') or '').strip()
        try:
            file_size = int(data.get('fileSize') or data.get('file_size') or 0)
        except (TypeError, ValueError):
            file_size = 0

        if not filename:
            return Response({'filename': 'filename 不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if file_size <= 0:
            return Response({'fileSize': 'fileSize 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_business_write_tenant(request)
        try:
            return Response(
                presign_video_put_url(
                    filename=filename,
                    content_type=content_type,
                    file_size=file_size,
                    tenant=tenant,
                )
            )
        except MinioConfigError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MinioSettingsView(APIView):
    permission_classes = [IsSuperUser]

    def _response_payload(self):
        cfg = MinioConfig.load()
        effective = get_minio_settings()
        return {
            'storageBackend': effective.storage_backend,
            'endpoint': effective.endpoint,
            'accessKey': effective.access_key,
            'bucketName': effective.bucket_name,
            'secure': effective.secure,
            'region': effective.region,
            'publicBaseUrl': effective.public_base_url,
            'r2AccountId': effective.r2_account_id,
            'r2AccessKeyId': effective.r2_access_key_id,
            'r2BucketName': effective.r2_bucket_name,
            'r2PublicBaseUrl': effective.r2_public_base_url,
            'videoMaxSizeMB': effective.video_max_size_bytes // (1024 * 1024),
            'allowVideoCloudUrl': effective.allow_video_cloud_url,
            'isActive': effective.is_active,
            'updated_at': cfg.updated_at,
        }

    def get(self, request):
        return Response(self._response_payload())

    def patch(self, request):
        instance = MinioConfig.load()
        serializer = MinioConfigSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._response_payload())


class MinioTenantQuotaView(APIView):
    permission_classes = [IsSuperUser]

    def _tenant_quotas(self):
        tenants = Tenant.objects.filter(is_active=True).order_by('id')
        quotas = []
        for tenant in tenants:
            quota, _ = TenantVideoQuota.objects.get_or_create(tenant=tenant, defaults={'quota_mb': None})
            quotas.append(quota)
        return quotas

    def get(self, request):
        serializer = TenantVideoQuotaSerializer(self._tenant_quotas(), many=True)
        return Response({'results': serializer.data})

    def patch(self, request):
        raw_items = request.data.get('items') if isinstance(request.data, dict) else None
        if not isinstance(raw_items, list):
            return Response({'items': 'items 必须是数组'}, status=status.HTTP_400_BAD_REQUEST)

        tenants = {tenant.id: tenant for tenant in Tenant.objects.filter(is_active=True)}
        for item in raw_items:
            if not isinstance(item, dict):
                return Response({'items': 'items 中每一项必须是对象'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                tenant_id = int(item.get('tenantId') or item.get('tenant_id'))
            except (TypeError, ValueError):
                return Response({'tenantId': 'tenantId 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)
            if tenant_id not in tenants:
                return Response({'tenantId': f'公司不存在或已停用：{tenant_id}'}, status=status.HTTP_400_BAD_REQUEST)
            quota_limited = bool(item.get('quotaLimited'))
            quota_mb = item.get('quotaMB')
            if not quota_limited:
                quota_mb = None
            else:
                try:
                    quota_mb = int(quota_mb)
                except (TypeError, ValueError):
                    return Response({'quotaMB': '启用限制时 quotaMB 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)
                if quota_mb <= 0:
                    return Response({'quotaMB': '启用限制时 quotaMB 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)
            TenantVideoQuota.objects.update_or_create(tenant=tenants[tenant_id], defaults={'quota_mb': quota_mb})

        serializer = TenantVideoQuotaSerializer(self._tenant_quotas(), many=True)
        return Response({'results': serializer.data})


SCROLLING_TEXT_LIST_PARAMETERS = [
    OpenApiParameter(
        name='title',
        description='按标题精确查询滚动文本。例如 title=首页滚动公告。适合前端按业务标题读取对应文本列表。',
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name='lang',
        description='localizedItems 返回语言。zh 返回中文，en 返回英文，其他值默认按 zh 处理。',
        required=False,
        type=str,
        enum=['zh', 'en'],
    ),
    OpenApiParameter(
        name='keyword',
        description='按标题、中文文本或英文文本模糊搜索，主要用于后台管理列表。',
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name='is_active',
        description='按启用状态过滤。true 仅返回启用，false 仅返回停用。',
        required=False,
        type=bool,
    ),
    OpenApiParameter(
        name='page',
        description='分页页码。默认使用系统分页配置。',
        required=False,
        type=int,
    ),
]

SCROLLING_TEXT_CONTENT_LANGUAGE_PARAMETER = OpenApiParameter(
    name='language',
    description='返回语言。cn 或 zh 返回中文字符串列表，en 返回英文字符串列表。不传则返回中英对象列表。',
    required=False,
    type=str,
    enum=['cn', 'zh', 'en'],
)

SCROLLING_TEXT_REQUEST_EXAMPLE = OpenApiExample(
    '新增滚动文本',
    value={
        'i18nScheme': 'zh_en',
        'items': [
            {'order': 1, 'zh': '欢迎参观', 'en': 'Welcome'},
            {'order': 2, 'zh': '请保持安静', 'en': 'Please keep quiet'},
        ],
    },
    request_only=True,
)

SCROLLING_TEXT_RESPONSE_EXAMPLE = OpenApiExample(
    '按标题和语言查询',
    value={
        'count': 1,
        'next': None,
        'previous': None,
        'results': [
            {
                'id': 1,
                'title': '首页滚动公告',
                'i18nScheme': 'zh_en',
                'i18nSchemeLabel': '中英',
                'isActive': True,
                'items': [
                    {'id': 1, 'order': 1, 'zh': '欢迎参观', 'en': 'Welcome'},
                    {'id': 2, 'order': 2, 'zh': '请保持安静', 'en': 'Please keep quiet'},
                ],
                'localizedItems': [
                    {'id': 1, 'order': 1, 'text': '欢迎参观'},
                    {'id': 2, 'order': 2, 'text': '请保持安静'},
                ],
                'created_at': '2026-05-07 15:00:00',
                'updated_at': '2026-05-07 15:00:00',
            }
        ],
    },
    response_only=True,
)

SCROLLING_TEXT_CONTENT_PAIR_EXAMPLE = OpenApiExample(
    '不传 language 的消费响应',
    value=[
        {'zh': '欢迎参观', 'en': 'Welcome'},
        {'zh': '请保持安静', 'en': 'Please keep quiet'},
    ],
    response_only=True,
)

SCROLLING_TEXT_CONTENT_LANGUAGE_EXAMPLE = OpenApiExample(
    '传 language=en 的消费响应',
    value=['Welcome', 'Please keep quiet'],
    response_only=True,
)

SCROLLING_TEXT_CONTENT_REQUEST_EXAMPLE = OpenApiExample(
    '请求英文内容',
    value={'language': 'en'},
    request_only=True,
)


def _publish_runtime_config_changed(tenant_id, event_type: str, reason: str) -> None:
    """后台资源变更后通知运行时设备刷新配置（统一走 device.runtime_config 订阅）。"""
    if tenant_id is None:
        return
    payload = {
        'type': event_type,
        'tenantId': tenant_id,
        'refresh': {
            'endpoint': '/api/v1/device-runtime/config/',
            'reason': reason,
        },
    }
    transaction.on_commit(lambda: publish_device_event_sync(payload))


@extend_schema_view(
    list=extend_schema(
        tags=['Resources'],
        summary='查询滚动文本列表 / 无参数获取消费文本',
        description=(
            '带 page、keyword、title、is_active、lang 等参数时返回后台管理分页列表。'
            '不传任何查询参数时，直接返回启用滚动文本的消费数组：'
            '`[{"zh":"中文内容","en":"English content"}]`。'
            '如果需要按请求体传 language 返回纯字符串列表，请使用 `POST /api/v1/resources/scrolling-texts/content/`。'
        ),
        parameters=SCROLLING_TEXT_LIST_PARAMETERS,
        examples=[SCROLLING_TEXT_RESPONSE_EXAMPLE, SCROLLING_TEXT_CONTENT_PAIR_EXAMPLE],
    ),
    retrieve=extend_schema(
        tags=['Resources'],
        summary='按 ID 查看滚动文本详情',
        description='后台管理详情接口。前端按业务标题读取时优先使用列表接口的 `title` 查询参数。',
    ),
    create=extend_schema(
        tags=['Resources'],
        summary='新增滚动文本',
        description='创建国际化方案和一组中英文本。第一版 `i18nScheme` 固定为 `zh_en`；标题可省略，省略时后端用第一条文本生成内部标题。',
        examples=[SCROLLING_TEXT_REQUEST_EXAMPLE],
    ),
    update=extend_schema(
        tags=['Resources'],
        summary='全量更新滚动文本',
        description='更新主记录并替换文本明细。items 会按传入 order 排序后重新编号；标题可省略，省略时保留原标题或按第一条文本生成。',
        examples=[SCROLLING_TEXT_REQUEST_EXAMPLE],
    ),
    partial_update=extend_schema(
        tags=['Resources'],
        summary='部分更新滚动文本',
        description='支持更新国际化方案和文本明细；传入 items 时会替换原有全部文本明细。启用状态默认由后台或管理端维护。',
        examples=[SCROLLING_TEXT_REQUEST_EXAMPLE],
    ),
    destroy=extend_schema(
        tags=['Resources'],
        summary='删除滚动文本',
        description='删除滚动文本主记录时会级联删除其全部中英文本明细。',
    ),
)
class ScrollingTextViewSet(CachedBusinessResponseMixin, PermissionMappedModelViewSet):
    # 仅启用 JWT（不禁用认证）：后台带 token 走 membership，运行时无 token 走 ?tenant=<code>。
    authentication_classes = [TenantAwareJWTAuthentication]
    permission_classes = [AllowAny]

    serializer_class = ScrollingTextSerializer
    lookup_field = 'pk'
    business_cache_namespace = 'scrolling_texts'
    permission_map = {}

    def get_permissions(self):
        """允许任何人访问，忽略父类基于 permission_map 的权限逻辑"""
        return [AllowAny()]

    def get_queryset(self):
        queryset = (
            ScrollingText.objects.prefetch_related(
                Prefetch('items', queryset=ScrollingTextItem.objects.order_by('order', 'id'))
            )
            .order_by('-updated_at', '-id')
        )
        title = self.request.query_params.get('title', '').strip()
        if title:
            queryset = queryset.filter(title=title)

        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword)
                | Q(items__zh_text__icontains=keyword)
                | Q(items__en_text__icontains=keyword)
            ).distinct()

        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')
        return scope_queryset_member_or_public(queryset, self.request)

    def perform_create(self, serializer):
        tenant = resolve_member_or_public_tenant(self.request)
        if tenant is not None:
            instance = serializer.save(tenant=tenant)
        else:
            instance = serializer.save()
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(getattr(instance, 'tenant_id', None), 'device.scrolling_texts.changed', 'scrollingTextsChanged')

    def perform_update(self, serializer):
        instance = serializer.save()
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(getattr(instance, 'tenant_id', None), 'device.scrolling_texts.changed', 'scrollingTextsChanged')

    def perform_destroy(self, instance):
        tenant_id = getattr(instance, 'tenant_id', None)
        super().perform_destroy(instance)
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(tenant_id, 'device.scrolling_texts.changed', 'scrollingTextsChanged')

    def list(self, request, *args, **kwargs):
        if not request.query_params:
            return Response(self.build_content_payload())
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        lang = self.request.query_params.get('lang', 'zh').strip().lower()
        context['lang'] = 'en' if lang == 'en' else 'zh'
        return context

    def build_content_payload(self, language: str = '') -> list:
        normalized_language = language.strip().lower()
        items = ScrollingTextItem.objects.filter(scrolling_text__is_active=True).order_by('scrolling_text__id', 'order', 'id')
        # 运行时消费路径同样按租户收窄（经 scrolling_text__tenant），否则滚动文本跨公司泄漏。
        user = getattr(self.request, 'user', None)
        if not (user is not None and user.is_authenticated and user.is_superuser):
            tenant = resolve_member_or_public_tenant(self.request)
            items = items.filter(scrolling_text__tenant=tenant) if tenant else items.none()
        if normalized_language in {'cn', 'zh'}:
            return [item.zh_text for item in items]
        if normalized_language == 'en':
            return [item.en_text for item in items]
        return [{'zh': item.zh_text, 'en': item.en_text} for item in items]

    @extend_schema(
        tags=['Resources'],
        summary='获取滚动文本消费列表',
        description=(
            '给前端展示滚动文本使用。GET 或 POST 均可；不传 language 时返回中英对象数组，'
            '传 `{"language":"cn"}` 或 `{"language":"zh"}` 返回中文字符串数组，'
            '传 `{"language":"en"}` 返回英文字符串数组。仅返回启用中的滚动文本。'
        ),
        parameters=[SCROLLING_TEXT_CONTENT_LANGUAGE_PARAMETER],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'language': {
                        'type': 'string',
                        'enum': ['cn', 'zh', 'en'],
                        'description': 'cn/zh 返回中文，en 返回英文；不传返回中英对象数组。',
                    }
                },
            }
        },
        examples=[SCROLLING_TEXT_CONTENT_REQUEST_EXAMPLE, SCROLLING_TEXT_CONTENT_PAIR_EXAMPLE, SCROLLING_TEXT_CONTENT_LANGUAGE_EXAMPLE],
    )
    @action(detail=False, methods=['get', 'post'], url_path='content')
    def content(self, request):
        language = request.data.get('language', '') if isinstance(request.data, dict) else ''
        if not language:
            language = request.query_params.get('language', '')
        return Response(self.build_content_payload(str(language)))


@extend_schema_view(
    list=extend_schema(tags=['Resources']),
    retrieve=extend_schema(tags=['Resources']),
    create=extend_schema(tags=['Resources']),
    update=extend_schema(tags=['Resources']),
    partial_update=extend_schema(tags=['Resources']),
    destroy=extend_schema(tags=['Resources']),
)
class VoiceToneViewSet(CachedBusinessResponseMixin, TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = VoiceToneSerializer
    lookup_field = 'pk'
    business_cache_namespace = 'voice_tones'
    permission_map = {
        'list': [CanViewVoiceTones],
        'retrieve': [CanViewVoiceTones],
        'create': [CanCreateVoiceTones],
        'update': [CanUpdateVoiceTones],
        'partial_update': [CanUpdateVoiceTones],
        'destroy': [CanDeleteVoiceTones],
    }

    def get_queryset(self):
        queryset = VoiceTone.objects.order_by('-updated_at', '-id')
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(voice_code__icontains=keyword))

        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(getattr(serializer.instance, 'tenant_id', None), 'device.voice_configuration.changed', 'voiceConfigurationChanged')

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(getattr(serializer.instance, 'tenant_id', None), 'device.voice_configuration.changed', 'voiceConfigurationChanged')

    def perform_destroy(self, instance):
        tenant_id = getattr(instance, 'tenant_id', None)
        super().perform_destroy(instance)
        self.clear_cached_business_responses()
        _publish_runtime_config_changed(tenant_id, 'device.voice_configuration.changed', 'voiceConfigurationChanged')


@extend_schema_view(
    list=extend_schema(tags=['Resources']),
    retrieve=extend_schema(tags=['Resources']),
    create=extend_schema(tags=['Resources']),
    update=extend_schema(tags=['Resources']),
    partial_update=extend_schema(tags=['Resources']),
    destroy=extend_schema(tags=['Resources']),
)
class ModelAssetViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = ModelAssetSerializer
    lookup_field = 'pk'
    permission_map = {
        'list': [CanViewModels],
        'retrieve': [CanViewModels],
        'create': [CanCreateModels],
        'update': [CanUpdateModels],
        'partial_update': [CanUpdateModels],
        'destroy': [CanDeleteModels],
    }

    def get_queryset(self):
        queryset = ModelAsset.objects.order_by('-updated_at', '-id')
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(cloud_url__icontains=keyword)
                | Q(model_file__icontains=keyword)
            )

        model_type = self.request.query_params.get('model_type', '').strip()
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        orientation = self.request.query_params.get('orientation', '').strip()
        if orientation:
            queryset = queryset.filter(orientation=orientation)

        is_visible = self.request.query_params.get('is_visible', '').strip().lower()
        if is_visible in {'true', 'false'}:
            queryset = queryset.filter(is_visible=is_visible == 'true')
        return self.apply_tenant_scope(queryset)


@extend_schema_view(
    list=extend_schema(tags=['Commands']),
    retrieve=extend_schema(tags=['Commands']),
    create=extend_schema(tags=['Commands']),
    update=extend_schema(tags=['Commands']),
    partial_update=extend_schema(tags=['Commands']),
    destroy=extend_schema(tags=['Commands']),
)
class CommandGroupViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = CommandGroupSerializer
    lookup_field = 'pk'
    permission_map = {
        'list': [CanViewCommandGroups],
        'retrieve': [CanViewCommandGroups],
        'create': [CanCreateCommandGroups],
        'update': [CanUpdateCommandGroups],
        'partial_update': [CanUpdateCommandGroups],
        'destroy': [CanDeleteCommandGroups],
    }

    def get_queryset(self):
        queryset = CommandGroup.objects.order_by('group_type', 'name', 'id')
        group_type = self.request.query_params.get('group_type', '').strip()
        if group_type:
            queryset = queryset.filter(group_type=group_type)
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        instance = serializer.save(**self.tenant_create_kwargs())
        enqueue_command_notification(
            'create',
            getattr(self.request, 'user', None),
            '指令分组',
            instance.name,
            extra_lines=[f'分组类型：{instance.get_group_type_display()}'],
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        enqueue_command_notification(
            'update',
            getattr(self.request, 'user', None),
            '指令分组',
            instance.name,
            extra_lines=[f'分组类型：{instance.get_group_type_display()}'],
        )

    def perform_destroy(self, instance):
        group_name = instance.name
        group_type = instance.get_group_type_display()
        user = getattr(self.request, 'user', None)
        super().perform_destroy(instance)
        enqueue_command_notification('delete', user, '指令分组', group_name, extra_lines=[f'分组类型：{group_type}'])


@extend_schema_view(
    list=extend_schema(tags=['Commands']),
    retrieve=extend_schema(tags=['Commands']),
    create=extend_schema(tags=['Commands']),
    update=extend_schema(tags=['Commands']),
    partial_update=extend_schema(tags=['Commands']),
    destroy=extend_schema(tags=['Commands']),
)
class ControlCommandViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = ControlCommandSerializer
    lookup_field = 'pk'
    permission_map = {
        'list': [CanViewControlCommands],
        'retrieve': [CanViewControlCommands],
        'create': [CanCreateControlCommands],
        'update': [CanUpdateControlCommands],
        'partial_update': [CanUpdateControlCommands],
        'destroy': [CanDeleteControlCommands],
    }

    def get_queryset(self):
        queryset = ControlCommand.objects.select_related('group').order_by('group__name', 'name', 'id')
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(command_code__icontains=keyword))
        group_id = self.request.query_params.get('group_id', '').strip()
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        instance = serializer.save(**self.tenant_create_kwargs())
        enqueue_command_change_notification(
            action='create',
            user=getattr(self.request, 'user', None),
            command_type='控制指令',
            name_before='',
            name_after=instance.name,
            command_code_before='',
            command_code_after=instance.command_code,
            group_name=instance.group.name if instance.group_id else '',
        )

    def perform_update(self, serializer):
        previous = serializer.instance
        # 仅当"名称"或"指令"字段发生变化时才发送飞书通知；
        # IP/端口/协议/启用状态等其它字段的变化不触发通知。
        name_before = previous.name if previous else ''
        code_before = previous.command_code if previous else ''
        instance = serializer.save()
        name_after = instance.name
        code_after = instance.command_code
        if name_before == name_after and code_before == code_after:
            return
        enqueue_command_change_notification(
            action='update',
            user=getattr(self.request, 'user', None),
            command_type='控制指令',
            name_before=name_before,
            name_after=name_after,
            command_code_before=code_before,
            command_code_after=code_after,
            group_name=instance.group.name if instance.group_id else '',
        )

    def perform_destroy(self, instance):
        command_name = instance.name
        command_code = instance.command_code
        group_name = instance.group.name if instance.group_id else ''
        user = getattr(self.request, 'user', None)
        super().perform_destroy(instance)
        enqueue_command_change_notification(
            action='delete',
            user=user,
            command_type='控制指令',
            name_before=command_name,
            name_after='',
            command_code_before=command_code,
            command_code_after='',
            group_name=group_name,
        )


@extend_schema_view(
    list=extend_schema(tags=['Commands']),
    retrieve=extend_schema(tags=['Commands']),
    create=extend_schema(tags=['Commands']),
    update=extend_schema(tags=['Commands']),
    partial_update=extend_schema(tags=['Commands']),
    destroy=extend_schema(tags=['Commands']),
)
class TaskCommandViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    serializer_class = TaskCommandSerializer
    lookup_field = 'pk'
    permission_map = {
        'list': [CanViewTaskCommands],
        'retrieve': [CanViewTaskCommands],
        'create': [CanCreateTaskCommands],
        'update': [CanUpdateTaskCommands],
        'partial_update': [CanUpdateTaskCommands],
        'destroy': [CanDeleteTaskCommands],
    }

    def get_queryset(self):
        inner_step_queryset = TaskCommandStep.objects.select_related('control_command', 'point', 'resource').order_by('order', 'id')
        step_queryset = (
            TaskCommandStep.objects.filter(parent__isnull=True)
            .select_related('control_command', 'point', 'resource')
            .prefetch_related(Prefetch('inner_tasks', queryset=inner_step_queryset))
            .order_by('order', 'id')
        )
        queryset = (
            TaskCommand.objects.select_related('group')
            .prefetch_related(Prefetch('tasks', queryset=step_queryset))
            .order_by('group__name', 'name', 'id')
        )
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(command_code__icontains=keyword))
        group_id = self.request.query_params.get('group_id', '').strip()
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        is_active = self.request.query_params.get('is_active', '').strip().lower()
        if is_active in {'true', 'false'}:
            queryset = queryset.filter(is_active=is_active == 'true')
        return self.apply_tenant_scope(queryset)

    def perform_create(self, serializer):
        instance = serializer.save(**self.tenant_create_kwargs())
        enqueue_command_change_notification(
            action='create',
            user=getattr(self.request, 'user', None),
            command_type='任务指令',
            name_before='',
            name_after=instance.name,
            command_code_before='',
            command_code_after=instance.command_code,
            group_name=instance.group.name if instance.group_id else '',
        )

    def perform_update(self, serializer):
        previous = serializer.instance
        # 仅当"名称"或"指令名称"字段发生变化时才发送飞书通知；
        # 子任务的增删改、是否启用等其它字段的变化不触发通知。
        name_before = previous.name if previous else ''
        code_before = previous.command_code if previous else ''
        instance = serializer.save()
        name_after = instance.name
        code_after = instance.command_code
        if name_before == name_after and code_before == code_after:
            return
        enqueue_command_change_notification(
            action='update',
            user=getattr(self.request, 'user', None),
            command_type='任务指令',
            name_before=name_before,
            name_after=name_after,
            command_code_before=code_before,
            command_code_after=code_after,
            group_name=instance.group.name if instance.group_id else '',
        )

    def perform_destroy(self, instance):
        command_name = instance.name
        command_code = instance.command_code
        group_name = instance.group.name if instance.group_id else ''
        user = getattr(self.request, 'user', None)
        super().perform_destroy(instance)
        enqueue_command_change_notification(
            action='delete',
            user=user,
            command_type='任务指令',
            name_before=command_name,
            name_after='',
            command_code_before=command_code,
            command_code_after='',
            group_name=group_name,
        )


@extend_schema(tags=['Commands'])
class CommandDataLookupView(APIView):
    # 仅启用 JWT（不禁用认证）：后台带 token 走 membership，运行时无 token 走 ?tenant=<code>。
    authentication_classes = [TenantAwareJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        command = request.query_params.get('command', '').strip()
        if not command:
            return Response(
                {'status': 'error', 'message': '指令不能为空', 'code': 40001, 'data': None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # command_code 现按租户唯一，必须先按租户收窄再查，否则会命中别家公司的同名指令。
        control_qs = scope_queryset_member_or_public(ControlCommand.objects.all(), request)
        control_command = control_qs.filter(command_code=command, is_active=True).select_related('group').first()
        if control_command and control_command.group and control_command.group.is_active:
            return Response(
                {
                    'status': 'success',
                    'message': 'success',
                    'code': 200,
                    'data': {
                        'commandType': 'control',
                        'name': control_command.name,
                        'command': control_command.command_code,
                        'commandValueType': control_command.command_value_type,
                        'callMethod': control_command.protocol,
                        'ip': control_command.host,
                        'port': control_command.port,
                    },
                }
            )

        # 运行时以 command 查询字符串为入口，可直接命中任务指令并返回完整子任务列表。
        inner_step_queryset = TaskCommandStep.objects.select_related('control_command', 'point', 'resource').order_by('order', 'id')
        step_queryset = (
            TaskCommandStep.objects.filter(parent__isnull=True)
            .select_related('control_command', 'point', 'resource')
            .prefetch_related(Prefetch('inner_tasks', queryset=inner_step_queryset))
            .order_by('order', 'id')
        )
        task_command = (
            scope_queryset_member_or_public(TaskCommand.objects.all(), request)
            .filter(command_code=command, is_active=True, group__is_active=True)
            .select_related('group')
            .prefetch_related(Prefetch('tasks', queryset=step_queryset))
            .first()
        )
        if task_command is None:
            return Response(
                {'status': 'error', 'message': '指令不存在', 'code': 40401, 'data': None},
                status=status.HTTP_404_NOT_FOUND,
            )

        tasks = [build_task_step_runtime_data(request, step) for step in task_command.tasks.all()]
        return Response(
            {
                'status': 'success',
                'message': 'success',
                'code': 200,
                'data': {
                    'commandType': 'task',
                    'name': task_command.name,
                    'command': task_command.command_code,
                    'tasks': tasks,
                    'command_list': build_task_command_list(list(task_command.tasks.all())),
                },
            }
        )


@extend_schema(tags=['Commands'])
class CommandExportEnabledGroupsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        groups = CommandGroup.objects.filter(export_enabled=True, is_active=True).order_by('group_type', 'name', 'id')
        return Response(
            {
                'status': 'success',
                'message': '导出成功',
                'data': CommandGroupSerializer(groups, many=True).data,
            }
        )


@extend_schema(tags=['Commands'])
class CommandExportCommandsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        control_commands = ControlCommand.objects.select_related('group').order_by('group__name', 'name', 'id')
        inner_step_queryset = TaskCommandStep.objects.select_related('control_command', 'point', 'resource').order_by('order', 'id')
        step_queryset = (
            TaskCommandStep.objects.filter(parent__isnull=True)
            .select_related('control_command', 'point', 'resource')
            .prefetch_related(Prefetch('inner_tasks', queryset=inner_step_queryset))
            .order_by('order', 'id')
        )
        task_commands = (
            TaskCommand.objects.select_related('group')
            .prefetch_related(Prefetch('tasks', queryset=step_queryset))
            .order_by('group__name', 'name', 'id')
        )
        return Response(
            {
                'status': 'success',
                'message': '导出成功',
                'data': {
                    'controlCommands': ControlCommandSerializer(control_commands, many=True).data,
                    'taskCommands': TaskCommandSerializer(task_commands, many=True, context={'request': request}).data,
                },
            }
        )
