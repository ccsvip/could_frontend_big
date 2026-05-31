from rest_framework import permissions

from .services.permissions import get_active_permission_codes_for_user


class IsAdminRole(permissions.BasePermission):
    message = '当前账号无管理权限'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class IsAuthenticatedReadOnlyOrAdminWrite(permissions.BasePermission):
    message = '当前账号无写入权限'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(user.is_staff or user.is_superuser)


class HasPermissionCode(permissions.BasePermission):
    message = '当前账号缺少所需权限'
    required_permission = ''

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not self.required_permission:
            return False

        return self.required_permission in get_active_permission_codes_for_user(user)


class CanViewAccountApplications(HasPermissionCode):
    required_permission = 'account_applications.view'


class CanReviewAccountApplications(HasPermissionCode):
    required_permission = 'account_applications.review'


class CanManageTenants(HasPermissionCode):
    # 平台超管专属：只有 superuser 的 access-context 才含 tenant.management.view。
    required_permission = 'tenant.management.view'


class CanManageEmployees(HasPermissionCode):
    # 公司管理员专属：tenant_admin 的 access-context 固有此码。
    required_permission = 'tenant.employees.manage'


class CanViewDevices(HasPermissionCode):
    required_permission = 'devices.view'


class CanCreateDevices(HasPermissionCode):
    required_permission = 'devices.create'


class CanUpdateDevices(HasPermissionCode):
    required_permission = 'devices.update'


class CanDeleteDevices(HasPermissionCode):
    required_permission = 'devices.delete'


class CanViewImageResources(HasPermissionCode):
    required_permission = 'resources.images.view'


class CanCreateImageResources(HasPermissionCode):
    required_permission = 'resources.images.create'


class CanUpdateImageResources(HasPermissionCode):
    required_permission = 'resources.images.update'


class CanDeleteImageResources(HasPermissionCode):
    required_permission = 'resources.images.delete'


class CanViewVideoResources(HasPermissionCode):
    required_permission = 'resources.videos.view'


class CanCreateVideoResources(HasPermissionCode):
    required_permission = 'resources.videos.create'


class CanUpdateVideoResources(HasPermissionCode):
    required_permission = 'resources.videos.update'


class CanDeleteVideoResources(HasPermissionCode):
    required_permission = 'resources.videos.delete'


class CanViewScrollingTexts(HasPermissionCode):
    required_permission = 'resources.scrolling_texts.view'


class CanCreateScrollingTexts(HasPermissionCode):
    required_permission = 'resources.scrolling_texts.create'


class CanUpdateScrollingTexts(HasPermissionCode):
    required_permission = 'resources.scrolling_texts.update'


class CanDeleteScrollingTexts(HasPermissionCode):
    required_permission = 'resources.scrolling_texts.delete'


class CanViewVoiceTones(HasPermissionCode):
    required_permission = 'resources.voice_tones.view'


class CanCreateVoiceTones(HasPermissionCode):
    required_permission = 'resources.voice_tones.create'


class CanUpdateVoiceTones(HasPermissionCode):
    required_permission = 'resources.voice_tones.update'


class CanDeleteVoiceTones(HasPermissionCode):
    required_permission = 'resources.voice_tones.delete'


class CanViewModels(HasPermissionCode):
    required_permission = 'resources.models.view'


class CanCreateModels(HasPermissionCode):
    required_permission = 'resources.models.create'


class CanUpdateModels(HasPermissionCode):
    required_permission = 'resources.models.update'


class CanDeleteModels(HasPermissionCode):
    required_permission = 'resources.models.delete'


class CanViewKnowledgeBase(HasPermissionCode):
    required_permission = 'knowledge_base.view'


class CanUploadKnowledgeBase(HasPermissionCode):
    required_permission = 'knowledge_base.upload'


class CanDownloadKnowledgeBase(HasPermissionCode):
    required_permission = 'knowledge_base.download'


class CanBulkDownloadKnowledgeBase(HasPermissionCode):
    required_permission = 'knowledge_base.bulk_download'


class CanViewControlCommands(HasPermissionCode):
    required_permission = 'commands.control.view'


class CanCreateControlCommands(HasPermissionCode):
    required_permission = 'commands.control.create'


class CanUpdateControlCommands(HasPermissionCode):
    required_permission = 'commands.control.update'


class CanDeleteControlCommands(HasPermissionCode):
    required_permission = 'commands.control.delete'


class CanViewCommandGroups(HasPermissionCode):
    required_permission = 'commands.groups.view'


class CanCreateCommandGroups(HasPermissionCode):
    required_permission = 'commands.groups.create'


class CanUpdateCommandGroups(HasPermissionCode):
    required_permission = 'commands.groups.update'


class CanDeleteCommandGroups(HasPermissionCode):
    required_permission = 'commands.groups.delete'


class CanViewTaskCommands(HasPermissionCode):
    required_permission = 'commands.tasks.view'


class CanCreateTaskCommands(HasPermissionCode):
    required_permission = 'commands.tasks.create'


class CanUpdateTaskCommands(HasPermissionCode):
    required_permission = 'commands.tasks.update'


class CanDeleteTaskCommands(HasPermissionCode):
    required_permission = 'commands.tasks.delete'


class CanViewCommandExports(HasPermissionCode):
    required_permission = 'commands.export.view'


class CanDownloadCommandExports(HasPermissionCode):
    required_permission = 'commands.export.download'


class CanViewAliyunCommands(HasPermissionCode):
    required_permission = 'commands.aliyun.view'


class CanViewPoints(HasPermissionCode):
    required_permission = 'commands.points.view'


class CanCreatePoints(HasPermissionCode):
    required_permission = 'commands.points.create'


class CanUpdatePoints(HasPermissionCode):
    required_permission = 'commands.points.update'


class CanDeletePoints(HasPermissionCode):
    required_permission = 'commands.points.delete'


class CanViewLLMProviders(HasPermissionCode):
    required_permission = 'ai_models.llm.view'


class CanCreateLLMProviders(HasPermissionCode):
    required_permission = 'ai_models.llm.create'


class CanUpdateLLMProviders(HasPermissionCode):
    required_permission = 'ai_models.llm.update'


class CanDeleteLLMProviders(HasPermissionCode):
    required_permission = 'ai_models.llm.delete'


class CanViewChat(HasPermissionCode):
    required_permission = 'ai_models.chat.view'


class CanCreateChat(HasPermissionCode):
    required_permission = 'ai_models.chat.create'


class CanDeleteChat(HasPermissionCode):
    required_permission = 'ai_models.chat.delete'


class CanViewKnowledgeBaseDocuments(HasPermissionCode):
    required_permission = 'knowledge_base.view'


class CanUploadKnowledgeBaseDocuments(HasPermissionCode):
    required_permission = 'knowledge_base.upload'


class CanDownloadKnowledgeBaseDocuments(HasPermissionCode):
    required_permission = 'knowledge_base.download'


class CanBulkDownloadKnowledgeBaseDocuments(HasPermissionCode):
    required_permission = 'knowledge_base.bulk_download'
