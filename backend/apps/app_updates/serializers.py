from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AppRelease, AppUpdateEvent


class AppUpdateCheckSerializer(serializers.Serializer):
    packageName = serializers.CharField(max_length=255)
    versionName = serializers.CharField(max_length=64)
    versionCode = serializers.IntegerField(min_value=0)
    versionInfo = serializers.CharField(max_length=255)

    def validate_packageName(self, value: str) -> str:
        expected = getattr(settings, 'APP_UPDATE_PACKAGE_NAME', 'com.solin.digital')
        if value != expected:
            raise serializers.ValidationError('应用包名不受支持')
        return value


class AppReleaseManagementSerializer(serializers.ModelSerializer):
    releaseId = serializers.CharField(source='release_id', read_only=True)
    packageName = serializers.CharField(source='package_name', read_only=True)
    versionName = serializers.CharField(source='version_name')
    versionCode = serializers.IntegerField(source='version_code', min_value=1)
    versionInfo = serializers.CharField(source='version_info')
    apkFile = serializers.FileField(source='apk_file', write_only=True, required=True)
    fileName = serializers.CharField(source='file_name', read_only=True)
    downloadUrl = serializers.SerializerMethodField()
    fileSize = serializers.IntegerField(source='file_size', read_only=True)
    forceUpgradeVersionCode = serializers.IntegerField(source='force_upgrade_version_code', min_value=0, read_only=True)
    releaseNotes = serializers.CharField(source='release_notes', allow_blank=True, required=False)
    isActive = serializers.BooleanField(source='is_active', required=False)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = AppRelease
        fields = (
            'releaseId', 'packageName', 'versionName', 'versionCode', 'versionInfo', 'apkFile',
            'fileName', 'downloadUrl', 'fileSize', 'sha256', 'forceUpgradeVersionCode',
            'releaseNotes', 'isActive', 'createdBy', 'createdAt', 'updatedAt',
        )
        read_only_fields = ('sha256',)

    def get_downloadUrl(self, obj: AppRelease) -> str:
        request = self.context.get('request')
        path = f'/api/v1/app-update-releases/{obj.release_id}/apk/'
        return request.build_absolute_uri(path) if request else path

    @staticmethod
    def get_createdBy(obj: AppRelease) -> str:
        if not obj.created_by:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.get_username()

    def validate(self, attrs):
        version_info = attrs.get('version_info', getattr(self.instance, 'version_info', ''))
        apk_file = attrs.get('apk_file')
        if apk_file and Path(apk_file.name).name != f'{version_info}.apk':
            raise serializers.ValidationError({'apkFile': f'APK 文件名必须为 {version_info}.apk'})
        return attrs

    def validate_versionCode(self, value: int) -> int:
        if AppRelease.objects.filter(version_code=value).exists():
            raise serializers.ValidationError('该内部版本号已存在')
        return value

    def validate_versionInfo(self, value: str) -> str:
        if AppRelease.objects.filter(version_info=value).exists():
            raise serializers.ValidationError('该完整版本标识已存在')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['package_name'] = getattr(settings, 'APP_UPDATE_PACKAGE_NAME', 'com.solin.digital')
        release = AppRelease(**validated_data, created_by=getattr(request, 'user', None))
        try:
            release.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, 'message_dict', exc.messages)) from exc
        return release

    def update(self, instance, validated_data):
        if set(validated_data) != {'is_active'}:
            raise serializers.ValidationError('发布后仅允许修改启用状态')
        instance.is_active = validated_data['is_active']
        instance.save(update_fields=['is_active', 'updated_at'])
        return instance


class AppUpdateReportSerializer(serializers.Serializer):
    releaseId = serializers.CharField(max_length=64)
    packageName = serializers.CharField(max_length=255)
    currentVersionCode = serializers.IntegerField(min_value=0)
    targetVersionCode = serializers.IntegerField(min_value=1)
    state = serializers.ChoiceField(choices=AppUpdateEvent.State.values)
    message = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)
    occurredAt = serializers.DateTimeField()

    def validate(self, attrs):
        try:
            release = AppRelease.objects.get(release_id=attrs['releaseId'])
        except AppRelease.DoesNotExist as exc:
            raise serializers.ValidationError({'releaseId': '发布记录不存在'}) from exc
        if attrs['packageName'] != release.package_name:
            raise serializers.ValidationError({'packageName': '应用包名与发布记录不一致'})
        if attrs['targetVersionCode'] != release.version_code:
            raise serializers.ValidationError({'targetVersionCode': '目标版本与发布记录不一致'})
        if attrs['currentVersionCode'] >= attrs['targetVersionCode']:
            raise serializers.ValidationError({'currentVersionCode': '更新前版本必须低于目标版本'})
        attrs['release'] = release
        return attrs

    def create_event(self, *, device):
        data = self.validated_data
        return AppUpdateEvent.objects.create(
            device=device,
            release=data['release'],
            package_name=data['packageName'],
            current_version_code=data['currentVersionCode'],
            target_version_code=data['targetVersionCode'],
            state=data['state'],
            message=data['message'],
            occurred_at=data['occurredAt'],
        )
