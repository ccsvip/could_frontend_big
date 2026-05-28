from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
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
    CanViewAliyunCommands,
    CanViewCommandGroups,
    CanViewControlCommands,
    CanViewImageResources,
    CanViewModels,
    CanViewScrollingTexts,
    CanViewTaskCommands,
    CanViewVideoResources,
    CanViewVoiceTones,
    IsAdminRole,
)
from config.business_cache import CachedBusinessResponseMixin

from .models import CommandGroup, ControlCommand, ModelAsset, Resource, ScrollingText, ScrollingTextItem, TaskCommand, TaskCommandStep, VoiceTone
from .serializers import (
    AliyunCommandItemSerializer,
    CommandGroupSerializer,
    ControlCommandSerializer,
    ModelAssetSerializer,
    ResourceSerializer,
    ScrollingTextSerializer,
    TaskCommandSerializer,
    VoiceToneSerializer,
    build_task_command_list,
    build_task_step_runtime_data,
)
from .services.aliyun_commands import (
    AliyunCommandConfigError,
    AliyunCommandServiceError,
    fetch_aliyun_commands,
)
from .tasks import enqueue_command_change_notification, enqueue_command_notification


class PermissionMappedModelViewSet(viewsets.ModelViewSet):
    permission_map = {}

    def get_permissions(self):
        permission_classes = self.permission_map.get(self.action, self.permission_map.get('list', []))
        return [permission() for permission in permission_classes]


class BaseResourceViewSet(CachedBusinessResponseMixin, PermissionMappedModelViewSet):
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
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['resource_type'] = self.resource_type
        return context


@extend_schema(tags=['Commands'])
class AliyunCommandListView(APIView):
    permission_classes = [CanViewAliyunCommands]

    def get(self, request):
        try:
            items = fetch_aliyun_commands()
        except AliyunCommandConfigError as exc:
            return Response(
                {
                    'status': 'error',
                    'message': str(exc),
                    'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except AliyunCommandServiceError as exc:
            return Response(
                {
                    'status': 'error',
                    'message': str(exc),
                    'code': status.HTTP_502_BAD_GATEWAY,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = AliyunCommandItemSerializer(items, many=True)
        return Response(
            {
                'status': 'success',
                'message': '获取阿里云指令列表成功',
                'data': {
                    'items': serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


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
    }


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
    authentication_classes = []
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
        return queryset

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
class VoiceToneViewSet(CachedBusinessResponseMixin, PermissionMappedModelViewSet):
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
        return queryset


@extend_schema_view(
    list=extend_schema(tags=['Resources']),
    retrieve=extend_schema(tags=['Resources']),
    create=extend_schema(tags=['Resources']),
    update=extend_schema(tags=['Resources']),
    partial_update=extend_schema(tags=['Resources']),
    destroy=extend_schema(tags=['Resources']),
)
class ModelAssetViewSet(PermissionMappedModelViewSet):
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
        return queryset


@extend_schema_view(
    list=extend_schema(tags=['Commands']),
    retrieve=extend_schema(tags=['Commands']),
    create=extend_schema(tags=['Commands']),
    update=extend_schema(tags=['Commands']),
    partial_update=extend_schema(tags=['Commands']),
    destroy=extend_schema(tags=['Commands']),
)
class CommandGroupViewSet(PermissionMappedModelViewSet):
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
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
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
class ControlCommandViewSet(PermissionMappedModelViewSet):
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
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
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
class TaskCommandViewSet(PermissionMappedModelViewSet):
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
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
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
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        command = request.query_params.get('command', '').strip()
        if not command:
            return Response(
                {'status': 'error', 'message': '指令不能为空', 'code': 40001, 'data': None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        control_command = ControlCommand.objects.filter(command_code=command, is_active=True).select_related('group').first()
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
            TaskCommand.objects.filter(command_code=command, is_active=True, group__is_active=True)
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
