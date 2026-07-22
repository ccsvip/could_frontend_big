from __future__ import annotations

from django.db import transaction

from apps.ai_models.models import BailianKnowledgeConfig, TenantKnowledgeModelSettings

from . import bailian


def tenant_category_name(tenant_id: int) -> str:
    return f'solin_t{tenant_id}'


def ensure_tenant_category(tenant_id: int) -> str:
    TenantKnowledgeModelSettings.objects.get_or_create(tenant_id=tenant_id)
    try:
        with transaction.atomic():
            tenant_settings = (
                TenantKnowledgeModelSettings.objects
                .select_for_update()
                .get(tenant_id=tenant_id)
            )
            if not tenant_settings.is_active or not tenant_settings.managed_rag_enabled:
                raise bailian.BailianKnowledgeError('当前公司尚未获得百炼托管知识库授权')

            platform_config = BailianKnowledgeConfig.load()
            if not platform_config.is_active or not platform_config.is_configured:
                raise bailian.BailianKnowledgeError('百炼托管知识库尚未由超管完成配置或启用')
            if (
                tenant_settings.bailian_category_id
                and tenant_settings.bailian_category_workspace_id == platform_config.workspace_id
            ):
                return tenant_settings.bailian_category_id

            category_name = tenant_category_name(tenant_id)
            category_id = bailian.find_category_by_name(category_name) or bailian.create_category(category_name)
            tenant_settings.bailian_category_id = category_id
            tenant_settings.bailian_category_workspace_id = platform_config.workspace_id
            tenant_settings.bailian_category_error = ''
            tenant_settings.save(update_fields=[
                'bailian_category_id',
                'bailian_category_workspace_id',
                'bailian_category_error',
                'updated_at',
            ])
            return category_id
    except Exception as exc:
        TenantKnowledgeModelSettings.objects.filter(tenant_id=tenant_id).update(
            bailian_category_error=str(exc)[:1000],
        )
        if isinstance(exc, bailian.BailianKnowledgeError):
            raise
        raise bailian.BailianKnowledgeError(f'自动创建公司百炼 Category 失败：{exc}') from exc
