from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.tenants.services import get_request_tenant

from .models import (
    CommandGroup,
    ControlCommand,
    ControlCommandRecognitionPolicy,
    ModelAsset,
    MinioConfig,
    Resource,
    ScrollingText,
    ScrollingTextItem,
    TaskCommand,
    TaskCommandStep,
    TenantVideoQuota,
    VoiceTone,
)
from .point_models import Point
from .services.minio_client import (
    MinioConfigError,
    build_public_object_url,
    delete_object,
    get_tenant_video_quota_summary,
    get_minio_settings,
    validate_tenant_object_key,
)
from .services.image_hashes import (
    DuplicateImageError,
    calculate_sha256,
    find_duplicate_image,
    normalize_sha256,
)


def build_absolute_file_url(request, file_field) -> str:
    if not file_field:
        return ''
    url = file_field.url
    return request.build_absolute_uri(url) if request else url


class ResourceSerializer(serializers.ModelSerializer):
    fileUrl = serializers.SerializerMethodField()
    fileName = serializers.SerializerMethodField()
    fileSize = serializers.SerializerMethodField()
    categoryLabel = serializers.CharField(source='get_category_display', read_only=True)
    resourceType = serializers.CharField(source='resource_type', read_only=True)
    resourceTypeLabel = serializers.CharField(source='get_resource_type_display', read_only=True)
    hasFile = serializers.BooleanField(source='has_file', read_only=True)
    cloudUrl = serializers.CharField(source='cloud_url', required=False, allow_blank=True, default='')
    storageBackend = serializers.CharField(source='storage_backend', required=False, allow_blank=True, default='')
    objectKey = serializers.CharField(source='object_key', required=False, allow_blank=True, default='')
    objectSize = serializers.IntegerField(source='object_size', required=False, allow_null=True, min_value=0)
    contentHash = serializers.CharField(source='content_hash', required=False, allow_blank=True)
    isDigitalHumanBackground = serializers.BooleanField(source='is_digital_human_background', required=False, default=False)
    clearFile = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Resource
        fields = (
            'id',
            'name',
            'resourceType',
            'resourceTypeLabel',
            'category',
            'categoryLabel',
            'description',
            'file',
            'cloudUrl',
            'storageBackend',
            'objectKey',
            'objectSize',
            'contentHash',
            'isDigitalHumanBackground',
            'fileUrl',
            'fileName',
            'fileSize',
            'hasFile',
            'clearFile',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'resourceType',
            'resourceTypeLabel',
            'fileUrl',
            'fileName',
            'fileSize',
            'hasFile',
            'created_at',
            'updated_at',
        )

    def get_fileUrl(self, obj: Resource) -> str:
        if obj.object_key:
            return build_public_object_url(obj.object_key, backend=obj.storage_backend)
        return build_absolute_file_url(self.context.get('request'), obj.file)

    def get_fileName(self, obj: Resource) -> str:
        if obj.object_key:
            return Path(obj.object_key).name
        if not obj.file:
            return ''
        return Path(obj.file.name).name

    def get_fileSize(self, obj: Resource) -> int | None:
        if obj.object_key:
            return obj.object_size
        if not obj.file:
            return None
        try:
            return obj.file.size
        except OSError:
            return None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        resource_type = self.context['resource_type']
        clear_file = attrs.pop('clearFile', False)
        request = self.context.get('request')
        tenant = self.context.get('object_key_tenant')
        if request is not None and not getattr(request, '_tenant_resolved', False):
            from apps.tenants.services import get_request_tenant

            tenant = tenant or get_request_tenant(request)
        object_key = attrs.get('object_key')
        if object_key:
            try:
                attrs['object_key'] = validate_tenant_object_key(object_key, tenant=tenant)
            except MinioConfigError as exc:
                raise serializers.ValidationError({'objectKey': str(exc)}) from exc
            if not attrs.get('storage_backend'):
                active_backend = get_minio_settings().storage_backend
                attrs['storage_backend'] = active_backend if active_backend == 'r2' else ''
        if resource_type == Resource.TYPE_IMAGE:
            uploaded_file = attrs.get('file')
            if uploaded_file:
                attrs['content_hash'] = calculate_sha256(uploaded_file)
            elif object_key:
                try:
                    attrs['content_hash'] = normalize_sha256(attrs.get('content_hash'))
                except ValueError as exc:
                    raise serializers.ValidationError({'contentHash': str(exc)}) from exc
            elif self.instance is None:
                attrs['content_hash'] = ''
            else:
                attrs.pop('content_hash', None)

            content_hash = attrs.get('content_hash')
            if content_hash:
                duplicate = find_duplicate_image(
                    tenant=tenant,
                    content_hash=content_hash,
                    exclude_id=self.instance.id if self.instance else None,
                )
                if duplicate is not None:
                    if object_key and not Resource.objects.filter(tenant=tenant, object_key=object_key).exists():
                        delete_object(object_key, backend=attrs.get('storage_backend', ''))
                    raise DuplicateImageError(duplicate)
        if resource_type == Resource.TYPE_VIDEO:
            minio_settings = get_minio_settings()
            submitted_cloud_url = (attrs.get('cloud_url') or '').strip()
            if submitted_cloud_url and not minio_settings.allow_video_cloud_url:
                raise serializers.ValidationError({'cloudUrl': '当前不允许填写视频云端 URL'})

            final_cloud_url = submitted_cloud_url
            if self.instance is not None and 'cloud_url' not in attrs:
                final_cloud_url = self.instance.cloud_url
            final_object_key = attrs.get('object_key')
            if self.instance is not None and 'object_key' not in attrs:
                final_object_key = self.instance.object_key
            final_has_uploaded_file = bool(attrs.get('file'))
            if self.instance is not None and 'file' not in attrs:
                final_has_uploaded_file = bool(self.instance.file)
            if final_cloud_url and (final_object_key or final_has_uploaded_file):
                raise serializers.ValidationError({'cloudUrl': '视频上传文件和云端 URL 只能二选一'})
            if not (final_cloud_url or final_object_key or final_has_uploaded_file):
                message = '请上传视频或填写云端 URL' if minio_settings.allow_video_cloud_url else '请上传视频'
                raise serializers.ValidationError({'file': message})
            # 视频来源必填；开启云端 URL 时仍与上传文件互斥。
            if clear_file:
                raise serializers.ValidationError({'clearFile': '视频资源不支持清空文件，请直接删除或重新上传'})
            attrs['is_digital_human_background'] = False

        attrs['resource_type'] = resource_type
        attrs['_clear_file'] = clear_file
        return attrs

    def create(self, validated_data):
        validated_data.pop('_clear_file', None)
        instance = Resource(**validated_data)
        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as exc:
            if instance.file:
                instance.file.delete(save=False)
            if instance.object_key:
                delete_object(instance.object_key, backend=instance.storage_backend)
            duplicate = find_duplicate_image(
                tenant=instance.tenant,
                content_hash=instance.content_hash,
            )
            if duplicate is None:
                raise
            raise DuplicateImageError(duplicate) from exc
        return instance

    def update(self, instance: Resource, validated_data):
        clear_file = validated_data.pop('_clear_file', False)
        new_object_key = validated_data.get('object_key')
        if new_object_key is not None and instance.object_key and new_object_key != instance.object_key:
            delete_object(instance.object_key, backend=instance.storage_backend)
        if clear_file:
            if instance.file:
                instance.file.delete(save=False)
            validated_data['file'] = None
            validated_data['content_hash'] = ''
        return super().update(instance, validated_data)


class ImageResourceBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError('ids 不允许重复')
        return value


class MinioConfigSerializer(serializers.ModelSerializer):
    storageBackend = serializers.ChoiceField(source='storage_backend', choices=MinioConfig.STORAGE_BACKEND_CHOICES, required=False)
    accessKey = serializers.CharField(source='access_key', required=False, allow_blank=True)
    secretKey = serializers.CharField(source='secret_key', required=False, allow_blank=True, write_only=True)
    bucketName = serializers.CharField(source='bucket_name', required=False, allow_blank=True)
    publicBaseUrl = serializers.CharField(source='public_base_url', required=False, allow_blank=True)
    r2AccountId = serializers.CharField(source='r2_account_id', required=False, allow_blank=True)
    r2AccessKeyId = serializers.CharField(source='r2_access_key_id', required=False, allow_blank=True)
    r2SecretAccessKey = serializers.CharField(source='r2_secret_access_key', required=False, allow_blank=True, write_only=True)
    r2BucketName = serializers.CharField(source='r2_bucket_name', required=False, allow_blank=True)
    r2PublicBaseUrl = serializers.CharField(source='r2_public_base_url', required=False, allow_blank=True)
    videoMaxSizeMB = serializers.IntegerField(source='video_max_size_mb', required=False, min_value=1)
    allowVideoCloudUrl = serializers.BooleanField(source='allow_video_cloud_url', required=False)
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = MinioConfig
        fields = (
            'endpoint',
            'storageBackend',
            'accessKey',
            'secretKey',
            'bucketName',
            'secure',
            'region',
            'publicBaseUrl',
            'r2AccountId',
            'r2AccessKeyId',
            'r2SecretAccessKey',
            'r2BucketName',
            'r2PublicBaseUrl',
            'videoMaxSizeMB',
            'allowVideoCloudUrl',
            'isActive',
            'updated_at',
        )
        read_only_fields = ('updated_at',)


class TenantVideoQuotaSerializer(serializers.ModelSerializer):
    tenantId = serializers.IntegerField(source='tenant_id', read_only=True)
    tenantName = serializers.CharField(source='tenant.name', read_only=True)
    tenantCode = serializers.CharField(source='tenant.code', read_only=True)
    quotaLimited = serializers.SerializerMethodField()
    quotaMB = serializers.IntegerField(source='quota_mb', required=False, allow_null=True, min_value=1)
    usedBytes = serializers.SerializerMethodField()
    usedMB = serializers.SerializerMethodField()
    remainingBytes = serializers.SerializerMethodField()
    remainingMB = serializers.SerializerMethodField()

    class Meta:
        model = TenantVideoQuota
        fields = (
            'tenantId',
            'tenantName',
            'tenantCode',
            'quotaLimited',
            'quotaMB',
            'usedBytes',
            'usedMB',
            'remainingBytes',
            'remainingMB',
            'updated_at',
        )
        read_only_fields = (
            'tenantId',
            'tenantName',
            'tenantCode',
            'quotaLimited',
            'usedBytes',
            'usedMB',
            'remainingBytes',
            'remainingMB',
            'updated_at',
        )

    def get_quotaLimited(self, obj: TenantVideoQuota) -> bool:
        return obj.quota_mb is not None

    def _summary(self, obj: TenantVideoQuota) -> dict:
        cache_name = '_video_quota_summary'
        if not hasattr(obj, cache_name):
            setattr(obj, cache_name, get_tenant_video_quota_summary(obj.tenant))
        return getattr(obj, cache_name)

    def get_usedBytes(self, obj: TenantVideoQuota):
        return self._summary(obj)['usedBytes']

    def get_usedMB(self, obj: TenantVideoQuota):
        return self._summary(obj)['usedMB']

    def get_remainingBytes(self, obj: TenantVideoQuota):
        return self._summary(obj)['remainingBytes']

    def get_remainingMB(self, obj: TenantVideoQuota):
        return self._summary(obj)['remainingMB']


class ScrollingTextItemSerializer(serializers.ModelSerializer):
    zh = serializers.CharField(source='zh_text')
    en = serializers.CharField(source='en_text')

    class Meta:
        model = ScrollingTextItem
        fields = ('id', 'order', 'zh', 'en')
        read_only_fields = ('id',)


class LocalizedScrollingTextItemSerializer(serializers.ModelSerializer):
    text = serializers.SerializerMethodField()

    class Meta:
        model = ScrollingTextItem
        fields = ('id', 'order', 'text')

    def get_text(self, obj: ScrollingTextItem) -> str:
        lang = self.context.get('lang', 'zh')
        return obj.en_text if lang == 'en' else obj.zh_text


class ScrollingTextSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False, allow_blank=True)
    i18nScheme = serializers.CharField(source='i18n_scheme', required=False, default=ScrollingText.I18N_SCHEME_ZH_EN)
    i18nSchemeLabel = serializers.CharField(source='get_i18n_scheme_display', read_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    items = ScrollingTextItemSerializer(many=True)
    localizedItems = serializers.SerializerMethodField()

    class Meta:
        model = ScrollingText
        fields = (
            'id',
            'title',
            'i18nScheme',
            'i18nSchemeLabel',
            'isActive',
            'items',
            'localizedItems',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'i18nSchemeLabel', 'localizedItems', 'created_at', 'updated_at')

    def get_localizedItems(self, obj: ScrollingText) -> list[dict]:
        lang = self.context.get('lang', 'zh')
        serializer = LocalizedScrollingTextItemSerializer(obj.items.all(), many=True, context={'lang': lang})
        return serializer.data

    def validate_i18nScheme(self, value: str) -> str:
        if value != ScrollingText.I18N_SCHEME_ZH_EN:
            raise serializers.ValidationError('当前仅支持中英国际化方案')
        return value

    def validate_items(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError('请至少配置一条滚动文本')

        for index, item in enumerate(value, start=1):
            zh_text = str(item.get('zh_text') or '').strip()
            en_text = str(item.get('en_text') or '').strip()
            if not zh_text:
                raise serializers.ValidationError(f'第 {index} 条中文文本不能为空')
            if not en_text:
                raise serializers.ValidationError(f'第 {index} 条英文文本不能为空')
            item['zh_text'] = zh_text
            item['en_text'] = en_text
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        title = str(attrs.get('title', self.instance.title if self.instance else '') or '').strip()
        if not title:
            items = attrs.get('items') or []
            first_item = items[0] if items else {}
            title = str(first_item.get('zh_text') or first_item.get('en_text') or '滚动文本').strip()
        attrs['title'] = title
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('items')
        scrolling_text = ScrollingText.objects.create(**validated_data)
        self._replace_items(scrolling_text, items)
        return scrolling_text

    @transaction.atomic
    def update(self, instance: ScrollingText, validated_data):
        items = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            self._replace_items(instance, items)
        return instance

    def _replace_items(self, scrolling_text: ScrollingText, items: list[dict]):
        normalized_items = sorted(items, key=lambda item: item.get('order') or 0)
        ScrollingTextItem.objects.bulk_create(
            [
                ScrollingTextItem(
                    scrolling_text=scrolling_text,
                    order=index,
                    zh_text=item['zh_text'],
                    en_text=item['en_text'],
                )
                for index, item in enumerate(normalized_items, start=1)
            ]
        )


class VoiceToneSerializer(serializers.ModelSerializer):
    voiceCode = serializers.CharField(source='voice_code')
    asrText = serializers.CharField(source='content', required=False, allow_blank=True, default='')
    iconUrl = serializers.SerializerMethodField()
    iconName = serializers.SerializerMethodField()
    iconSize = serializers.SerializerMethodField()
    hasIcon = serializers.BooleanField(source='has_icon', read_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    isVisible = serializers.BooleanField(source='is_visible', required=False, default=True)
    audioUrl = serializers.SerializerMethodField()
    audioName = serializers.SerializerMethodField()
    audioSize = serializers.SerializerMethodField()
    hasAudio = serializers.BooleanField(source='has_audio', read_only=True)
    clearIcon = serializers.BooleanField(write_only=True, required=False, default=False)
    clearAudio = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = VoiceTone
        fields = (
            'id',
            'name',
            'voiceCode',
            'asrText',
            'icon',
            'iconUrl',
            'iconName',
            'iconSize',
            'hasIcon',
            'audio',
            'audioUrl',
            'audioName',
            'audioSize',
            'hasAudio',
            'isActive',
            'isVisible',
            'clearIcon',
            'clearAudio',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'iconUrl',
            'iconName',
            'iconSize',
            'hasIcon',
            'audioUrl',
            'audioName',
            'audioSize',
            'hasAudio',
            'created_at',
            'updated_at',
        )

    def get_iconUrl(self, obj) -> str:
        return build_absolute_file_url(self.context.get('request'), obj.icon)

    def get_iconName(self, obj) -> str:
        return Path(obj.icon.name).name if obj.icon else ''

    def get_iconSize(self, obj) -> int | None:
        if not obj.icon:
            return None
        try:
            return obj.icon.size
        except OSError:
            return None

    def get_audioUrl(self, obj) -> str:
        return build_absolute_file_url(self.context.get('request'), obj.audio)

    def get_audioName(self, obj) -> str:
        return Path(obj.audio.name).name if obj.audio else ''

    def get_audioSize(self, obj) -> int | None:
        if not obj.audio:
            return None
        try:
            return obj.audio.size
        except OSError:
            return None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        clear_icon = attrs.pop('clearIcon', False)
        clear_audio = attrs.pop('clearAudio', False)
        voice_code = attrs.get('voice_code')

        if voice_code:
            queryset = self.Meta.model.objects.filter(voice_code=voice_code)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'voiceCode': '该音色标识已存在'})

        attrs['_clear_icon'] = clear_icon
        attrs['_clear_audio'] = clear_audio
        return attrs

    def create(self, validated_data):
        validated_data.pop('_clear_icon', None)
        validated_data.pop('_clear_audio', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        clear_icon = validated_data.pop('_clear_icon', False)
        clear_audio = validated_data.pop('_clear_audio', False)
        if clear_icon:
            if instance.icon:
                instance.icon.delete(save=False)
            validated_data['icon'] = None
        if clear_audio:
            if instance.audio:
                instance.audio.delete(save=False)
            validated_data['audio'] = None
        return super().update(instance, validated_data)


class ModelAssetSerializer(serializers.ModelSerializer):
    modelType = serializers.CharField(source='model_type')
    modelTypeLabel = serializers.CharField(source='get_model_type_display', read_only=True)
    orientationLabel = serializers.CharField(source='get_orientation_display', read_only=True)
    thumbnailUrl = serializers.SerializerMethodField()
    thumbnailName = serializers.SerializerMethodField()
    hasThumbnail = serializers.BooleanField(source='has_thumbnail', read_only=True)
    modelFileName = serializers.SerializerMethodField()
    modelSize = serializers.IntegerField(source='model_size', read_only=True)
    hasModelFile = serializers.BooleanField(source='has_model_file', read_only=True)
    localUrl = serializers.SerializerMethodField()
    cloudUrl = serializers.CharField(source='cloud_url', required=False, allow_blank=True, default='')
    effectiveUrl = serializers.SerializerMethodField()
    isVisible = serializers.BooleanField(source='is_visible', required=False, default=True)
    clearThumbnail = serializers.BooleanField(write_only=True, required=False, default=False)
    clearModelFile = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = ModelAsset
        fields = (
            'id',
            'name',
            'modelType',
            'modelTypeLabel',
            'orientation',
            'orientationLabel',
            'thumbnail',
            'thumbnailUrl',
            'thumbnailName',
            'hasThumbnail',
            'model_file',
            'modelFileName',
            'modelSize',
            'hasModelFile',
            'localUrl',
            'cloudUrl',
            'effectiveUrl',
            'isVisible',
            'clearThumbnail',
            'clearModelFile',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'modelTypeLabel',
            'orientationLabel',
            'thumbnailUrl',
            'thumbnailName',
            'hasThumbnail',
            'modelFileName',
            'modelSize',
            'hasModelFile',
            'localUrl',
            'effectiveUrl',
            'created_at',
            'updated_at',
        )
        extra_kwargs = {'name': {'validators': []}}

    def get_thumbnailUrl(self, obj: ModelAsset) -> str:
        return build_absolute_file_url(self.context.get('request'), obj.thumbnail)

    def get_thumbnailName(self, obj: ModelAsset) -> str:
        return Path(obj.thumbnail.name).name if obj.thumbnail else ''

    def get_modelFileName(self, obj: ModelAsset) -> str:
        return Path(obj.model_file.name).name if obj.model_file else ''

    def get_localUrl(self, obj: ModelAsset) -> str:
        return build_absolute_file_url(self.context.get('request'), obj.model_file)

    def get_effectiveUrl(self, obj: ModelAsset) -> str:
        return self.get_localUrl(obj) or obj.cloud_url or ''

    def validate(self, attrs):
        attrs = super().validate(attrs)
        clear_thumbnail = attrs.pop('clearThumbnail', False)
        clear_model_file = attrs.pop('clearModelFile', False)

        name = attrs.get('name')
        if name:
            queryset = self.Meta.model.objects.filter(name=name)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'name': '该模型名称已存在'})

        instance_has_model_file = bool(self.instance and self.instance.model_file)
        has_model_file = bool(attrs.get('model_file')) or (instance_has_model_file and not clear_model_file)
        cloud_url = attrs.get('cloud_url') if 'cloud_url' in attrs else (self.instance.cloud_url if self.instance else '')
        if not has_model_file and not cloud_url:
            raise serializers.ValidationError({'cloudUrl': '请上传模型文件或填写云端地址'})

        attrs['_clear_thumbnail'] = clear_thumbnail
        attrs['_clear_model_file'] = clear_model_file
        return attrs

    def create(self, validated_data):
        validated_data.pop('_clear_thumbnail', None)
        validated_data.pop('_clear_model_file', None)
        return super().create(validated_data)

    def update(self, instance: ModelAsset, validated_data):
        clear_thumbnail = validated_data.pop('_clear_thumbnail', False)
        clear_model_file = validated_data.pop('_clear_model_file', False)
        if clear_thumbnail:
            if instance.thumbnail:
                instance.thumbnail.delete(save=False)
            validated_data['thumbnail'] = None
        if clear_model_file:
            if instance.model_file:
                instance.model_file.delete(save=False)
            validated_data['model_file'] = None
        return super().update(instance, validated_data)


class CommandGroupSerializer(serializers.ModelSerializer):
    groupType = serializers.CharField(source='group_type')
    groupTypeLabel = serializers.CharField(source='get_group_type_display', read_only=True)
    exportEnabled = serializers.BooleanField(source='export_enabled', required=False, default=False)
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)

    class Meta:
        model = CommandGroup
        fields = (
            'id',
            'name',
            'groupType',
            'groupTypeLabel',
            'exportEnabled',
            'isActive',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'groupTypeLabel', 'created_at', 'updated_at')

    def validate_groupType(self, value: str) -> str:
        if value not in {CommandGroup.TYPE_CONTROL, CommandGroup.TYPE_TASK}:
            raise serializers.ValidationError('请选择控制指令或任务指令')
        return value


class ControlCommandSerializer(serializers.ModelSerializer):
    groupId = serializers.PrimaryKeyRelatedField(source='group', queryset=CommandGroup.objects.all())
    groupName = serializers.CharField(source='group.name', read_only=True)
    command = serializers.CharField(source='command_code')
    commandValueType = serializers.CharField(source='command_value_type', required=False, default=ControlCommand.COMMAND_VALUE_TYPE_STRING)
    ip = serializers.IPAddressField(source='host')
    callMethod = serializers.CharField(source='protocol')
    backendSendEnabled = serializers.BooleanField(source='backend_send_enabled', required=False, default=False)
    executionReply = serializers.CharField(source='execution_reply', required=False, allow_blank=True, trim_whitespace=True)
    replyStrategy = serializers.ChoiceField(
        source='reply_strategy',
        choices=ControlCommand.REPLY_STRATEGY_CHOICES,
        required=False,
        default=ControlCommand.REPLY_STRATEGY_FIXED,
    )
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)

    class Meta:
        model = ControlCommand
        fields = (
            'id',
            'groupId',
            'groupName',
            'name',
            'command',
            'commandValueType',
            'ip',
            'port',
            'callMethod',
            'backendSendEnabled',
            'executionReply',
            'replyStrategy',
            'isActive',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'groupName', 'created_at', 'updated_at')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get('group', self.instance.group if self.instance else None)
        if group is None or group.group_type != CommandGroup.TYPE_CONTROL:
            raise serializers.ValidationError({'groupId': '请选择控制指令类型的指令管理'})

        request_tenant = get_request_tenant(self.context.get('request'))
        if request_tenant is not None and group.tenant_id != request_tenant.id:
            raise serializers.ValidationError({'groupId': '请选择当前公司的控制指令管理'})

        command_code = attrs.get('command_code')
        if command_code:
            queryset = self.Meta.model.objects.filter(
                tenant_id=group.tenant_id,
                command_code=command_code,
            )
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'command': '该指令已存在'})

        protocol = attrs.get('protocol', self.instance.protocol if self.instance else ControlCommand.PROTOCOL_UDP)
        if protocol not in {ControlCommand.PROTOCOL_UDP, ControlCommand.PROTOCOL_TCP}:
            raise serializers.ValidationError({'callMethod': '调用方式只能是 UDP 或 TCP'})
        command_value_type = attrs.get(
            'command_value_type',
            self.instance.command_value_type if self.instance else ControlCommand.COMMAND_VALUE_TYPE_STRING,
        )
        if command_value_type not in {
            ControlCommand.COMMAND_VALUE_TYPE_STRING,
            ControlCommand.COMMAND_VALUE_TYPE_HEX,
            ControlCommand.COMMAND_VALUE_TYPE_ASCII,
        }:
            raise serializers.ValidationError({'commandValueType': '请选择字符串、16进制或 ascii'})
        return attrs


class ControlCommandRecognitionPolicySerializer(serializers.ModelSerializer):
    fixedExecutionReply = serializers.CharField(
        source='fixed_execution_reply',
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=500,
    )
    directExecutionThreshold = serializers.DecimalField(
        source='direct_execution_threshold',
        max_digits=3,
        decimal_places=2,
        min_value=Decimal('0.90'),
        max_value=Decimal('1.00'),
    )
    llmConfirmationThreshold = serializers.DecimalField(
        source='llm_confirmation_threshold',
        max_digits=3,
        decimal_places=2,
        min_value=Decimal('0.50'),
        max_value=Decimal('1.00'),
    )

    class Meta:
        model = ControlCommandRecognitionPolicy
        fields = ('fixedExecutionReply', 'directExecutionThreshold', 'llmConfirmationThreshold')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        direct_threshold = attrs.get(
            'direct_execution_threshold',
            self.instance.direct_execution_threshold if self.instance else None,
        )
        confirmation_threshold = attrs.get(
            'llm_confirmation_threshold',
            self.instance.llm_confirmation_threshold if self.instance else None,
        )
        if confirmation_threshold is not None and direct_threshold is not None and confirmation_threshold > direct_threshold:
            raise serializers.ValidationError({'llmConfirmationThreshold': 'LLM 确认阈值不能高于直接执行阈值'})
        return attrs


class TaskCommandStepsField(serializers.Field):
    def to_representation(self, value):
        steps = list(value.all()) if hasattr(value, 'all') else list(value or [])
        root_steps = sorted(
            (step for step in steps if step.parent_id is None),
            key=lambda step: (step.order, step.id),
        )
        return TaskCommandStepSerializer(root_steps, many=True, context=self.parent.context).data

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError('请至少配置一个子任务')
        serializer = TaskCommandStepSerializer(data=data, many=True, context={**self.parent.context, 'inner_depth': 0})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class InnerTaskStepsField(serializers.Field):
    def to_representation(self, value):
        steps = list(value.all()) if hasattr(value, 'all') else list(value or [])
        ordered_steps = sorted(steps, key=lambda step: (step.order, step.id))
        return TaskCommandStepSerializer(
            ordered_steps,
            many=True,
            context={**self.parent.context, 'inner_depth': self.parent.context.get('inner_depth', 0) + 1},
        ).data

    def to_internal_value(self, data):
        if data in (None, ''):
            return []
        if not isinstance(data, list):
            raise serializers.ValidationError('子子任务必须是列表')
        serializer = TaskCommandStepSerializer(
            data=data,
            many=True,
            context={**self.parent.context, 'inner_depth': self.parent.context.get('inner_depth', 0) + 1},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class TaskCommandStepSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='task_type')
    delaySeconds = serializers.IntegerField(source='delay_seconds', required=False, default=0, min_value=0)
    waitForInnerTasks = serializers.BooleanField(source='wait_for_inner_tasks', required=False, default=False)
    isShow = serializers.BooleanField(source='is_show', required=False, default=True)
    controlCommandId = serializers.PrimaryKeyRelatedField(
        source='control_command',
        queryset=ControlCommand.objects.all(),
        required=False,
        allow_null=True,
    )
    pointId = serializers.PrimaryKeyRelatedField(source='point', queryset=Point.objects.all(), required=False, allow_null=True)
    resourceId = serializers.PrimaryKeyRelatedField(
        source='resource',
        queryset=Resource.objects.all(),
        required=False,
        allow_null=True,
    )
    text = serializers.CharField(source='text_content', required=False, allow_blank=True)
    imageText = serializers.CharField(source='image_text', required=False, allow_blank=True, default='')
    innerTasks = InnerTaskStepsField(source='inner_tasks', required=False)
    content = serializers.SerializerMethodField()

    class Meta:
        model = TaskCommandStep
        fields = (
            'id',
            'order',
            'type',
            'delaySeconds',
            'waitForInnerTasks',
            'isShow',
            'controlCommandId',
            'pointId',
            'resourceId',
            'text',
            'imageText',
            'innerTasks',
            'content',
        )
        read_only_fields = ('id', 'content')

    def validate_type(self, value: str) -> str:
        if value not in {choice[0] for choice in TaskCommandStep.TYPE_CHOICES}:
            raise serializers.ValidationError('请选择合法的子任务类型')
        if self.context.get('inner_depth', 0) > 0 and value == TaskCommandStep.TYPE_NAVIGATION:
            raise serializers.ValidationError('子子任务不能选择导航指令')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        task_type = attrs.get('task_type', self.instance.task_type if self.instance else '')
        control_command = attrs.get('control_command', self.instance.control_command if self.instance else None)
        point = attrs.get('point', self.instance.point if self.instance else None)
        resource = attrs.get('resource', self.instance.resource if self.instance else None)
        text_content = attrs.get('text_content', self.instance.text_content if self.instance else '')
        image_text = attrs.get('image_text', self.instance.image_text if self.instance else '')
        inner_tasks = attrs.get('inner_tasks', [])
        wait_for_inner_tasks = attrs.get('wait_for_inner_tasks', self.instance.wait_for_inner_tasks if self.instance else False)
        is_show = attrs.get('is_show', self.instance.is_show if self.instance else True)

        if task_type == TaskCommandStep.TYPE_COMMAND and control_command is None:
            raise serializers.ValidationError({'controlCommandId': '请选择控制指令'})
        if task_type == TaskCommandStep.TYPE_NAVIGATION and point is None:
            raise serializers.ValidationError({'pointId': '请选择点位'})
        if task_type in {TaskCommandStep.TYPE_IMAGE, TaskCommandStep.TYPE_VIDEO}:
            if resource is None:
                raise serializers.ValidationError({'resourceId': '请选择资源'})
            expected_type = Resource.TYPE_IMAGE if task_type == TaskCommandStep.TYPE_IMAGE else Resource.TYPE_VIDEO
            if resource.resource_type != expected_type:
                raise serializers.ValidationError({'resourceId': '资源类型与子任务类型不一致'})
        if task_type == TaskCommandStep.TYPE_TEXT and not str(text_content or '').strip():
            raise serializers.ValidationError({'text': '请输入文本内容'})
        if task_type != TaskCommandStep.TYPE_NAVIGATION and inner_tasks:
            raise serializers.ValidationError({'innerTasks': '只有导航指令可以配置子子任务'})
        attrs['image_text'] = str(image_text or '').strip() if task_type == TaskCommandStep.TYPE_IMAGE else ''
        attrs['inner_tasks'] = inner_tasks if task_type == TaskCommandStep.TYPE_NAVIGATION else []
        attrs['wait_for_inner_tasks'] = bool(wait_for_inner_tasks) if task_type == TaskCommandStep.TYPE_NAVIGATION else False
        # is_show 是导航子任务专属开关；其它类型保持为 True，避免过滤逻辑误伤。
        attrs['is_show'] = bool(is_show) if task_type == TaskCommandStep.TYPE_NAVIGATION else True
        return attrs

    def get_content(self, obj: TaskCommandStep) -> dict:
        return build_task_step_content(self.context.get('request'), obj)


class TaskCommandSerializer(serializers.ModelSerializer):
    groupId = serializers.PrimaryKeyRelatedField(source='group', queryset=CommandGroup.objects.all())
    groupName = serializers.CharField(source='group.name', read_only=True)
    command = serializers.CharField(source='command_code')
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    tasks = TaskCommandStepsField()

    class Meta:
        model = TaskCommand
        fields = (
            'id',
            'groupId',
            'groupName',
            'name',
            'command',
            'isActive',
            'tasks',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'groupName', 'created_at', 'updated_at')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        group = attrs.get('group', self.instance.group if self.instance else None)
        if group is None or group.group_type != CommandGroup.TYPE_TASK:
            raise serializers.ValidationError({'groupId': '请选择任务指令类型的指令管理'})

        command_code = attrs.get('command_code')
        if command_code:
            queryset = self.Meta.model.objects.filter(command_code=command_code)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({'command': '该指令已存在'})

        tasks = attrs.get('tasks')
        if not tasks:
            raise serializers.ValidationError({'tasks': '请至少配置一个子任务'})
        self._validate_task_orders(tasks)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tasks = validated_data.pop('tasks')
        command = TaskCommand.objects.create(**validated_data)
        self._replace_tasks(command, tasks)
        return command

    @transaction.atomic
    def update(self, instance: TaskCommand, validated_data):
        tasks = validated_data.pop('tasks')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.tasks.all().delete()
        self._replace_tasks(instance, tasks)
        return instance

    def _replace_tasks(self, command: TaskCommand, tasks: list[dict]):
        normalized_tasks = sorted(tasks, key=lambda item: item['order'])
        for index, task in enumerate(normalized_tasks, start=1):
            self._create_task_step(command, task, index)

    def _create_task_step(self, command: TaskCommand, task: dict, order: int, parent: TaskCommandStep | None = None) -> TaskCommandStep:
        is_navigation = task['task_type'] == TaskCommandStep.TYPE_NAVIGATION
        step = TaskCommandStep.objects.create(
            task_command=command,
            parent=parent,
            order=order,
            task_type=task['task_type'],
            delay_seconds=task.get('delay_seconds') or 0,
            wait_for_inner_tasks=bool(task.get('wait_for_inner_tasks')) if is_navigation else False,
            is_show=bool(task.get('is_show', True)) if is_navigation else True,
            control_command=task.get('control_command'),
            point=task.get('point'),
            resource=task.get('resource'),
            text_content=str(task.get('text_content') or '').strip(),
            image_text=str(task.get('image_text') or '').strip() if task['task_type'] == TaskCommandStep.TYPE_IMAGE else '',
        )
        inner_tasks = sorted(task.get('inner_tasks') or [], key=lambda item: item['order'])
        for inner_index, inner_task in enumerate(inner_tasks, start=1):
            self._create_task_step(command, inner_task, inner_index, parent=step)
        return step

    def _validate_task_orders(self, tasks: list[dict], field: str = 'tasks'):
        orders = [item['order'] for item in tasks]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError({field: '子任务顺序不能重复'})
        for task in tasks:
            inner_tasks = task.get('inner_tasks') or []
            if inner_tasks:
                inner_orders = [item['order'] for item in inner_tasks]
                if len(inner_orders) != len(set(inner_orders)):
                    raise serializers.ValidationError({field: '子子任务顺序不能重复'})


def build_resource_url(request, resource: Resource) -> str:
    return build_absolute_file_url(request, resource.file) or resource.cloud_url or ''


def build_task_step_content(request, step: TaskCommandStep) -> dict:
    if step.task_type == TaskCommandStep.TYPE_COMMAND and step.control_command:
        command = step.control_command
        return {
            'id': command.id,
            'name': command.name,
            'command': command.command_code,
            'commandType': 'control',
            'commandValueType': command.command_value_type,
            'callMethod': command.protocol,
            'backendSendEnabled': command.backend_send_enabled,
            'ip': command.host,
            'port': command.port,
        }
    if step.task_type == TaskCommandStep.TYPE_NAVIGATION and step.point:
        return {
            'id': step.point.id,
            'pointName': step.point.name,
            'command': step.point.command,
        }
    if step.task_type in {TaskCommandStep.TYPE_IMAGE, TaskCommandStep.TYPE_VIDEO} and step.resource:
        content = {
            'id': step.resource.id,
            'name': step.resource.name,
            'url': build_resource_url(request, step.resource),
        }
        if step.task_type == TaskCommandStep.TYPE_IMAGE:
            content['imageText'] = step.image_text or ''
        return content
    if step.task_type == TaskCommandStep.TYPE_TEXT:
        return {'text': step.text_content}
    return {}


def build_task_step_runtime_data(request, step: TaskCommandStep) -> dict:
    data = {
        'order': step.order,
        'type': step.task_type,
        'delaySeconds': step.delay_seconds,
        'content': build_task_step_content(request, step),
    }
    if step.task_type == TaskCommandStep.TYPE_NAVIGATION:
        # step_id 与 command_list[i].step_id 一一对应；即便同一点位被多次引用，
        # 它们的 step_id 也是数据库主键自增、永不重复，方便前端精确锁定。
        data['step_id'] = step.id
        data['wait_for_inner_tasks'] = step.wait_for_inner_tasks
        data['is_show'] = step.is_show
        inner_steps = sorted(list(step.inner_tasks.all()), key=lambda item: (item.order, item.id))
        if inner_steps:
            data['inner_tasks'] = [build_task_step_runtime_data(request, inner_step) for inner_step in inner_steps]
    return data


def build_task_command_list(steps: list[TaskCommandStep]) -> list[dict]:
    """根据任务指令的顶层子任务，提炼出导航子任务的点位映射表。

    返回结构与运行时点位跳过逻辑对齐：
    [{'step_id': <子任务主键>, 'point_name': <点位标题>, 'command_key': <点位命令>, 'is_show': <是否显示到前端>}]

    过滤规则：
    - 只收集 task_type == navigation 且关联了 point 的子任务；
    - is_show 为 False 的导航子任务不进入 command_list（前端只渲染允许显示的点位）；
      注意 tasks 数组不做这层过滤，仍会返回完整的导航子任务（含 is_show=False 的条目）。

    step_id 是 TaskCommandStep 的数据库自增主键：
    - 与 tasks[i].step_id 一一对应，可在两个列表间唯一匹配；
    - 同一点位被同一任务多次引用时，对应不同的 step_id，前端不会混淆；
    - 删除后再新增的导航子任务也会拿到新的、单调递增的 ID，旧 ID 不会复用。
    """
    items: list[dict] = []
    for step in steps:
        if step.task_type != TaskCommandStep.TYPE_NAVIGATION or step.point is None:
            continue
        if not step.is_show:
            continue
        items.append(
            {
                'step_id': step.id,
                'point_name': step.point.name,
                'command_key': step.point.command,
                'is_show': step.is_show,
            }
        )
    return items


class CommandDataLookupSerializer(serializers.Serializer):
    commandType = serializers.CharField()
    name = serializers.CharField()
    command = serializers.CharField()
    tasks = serializers.ListField(child=serializers.DictField(), required=False)
