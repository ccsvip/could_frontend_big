"""隔离契约守护测试（防回归）。

目的：当未来有人给某个模型加了 `tenant` 外键、却忘了挂 TenantManager（于是
`.objects.for_tenant()` 不存在、裸 `.objects.all()` 会跨租户），本测试立即失败，
把「忘记隔离」从线上泄漏变成 CI 红灯。

这是 PR 计划里的头号风险 R1 的自动化护栏。新增 tenant-scoped 模型时：
- 要么让它用 TenantManager（默认要求）；
- 要么在 KNOWN_NON_SCOPED_EXEMPTIONS 里显式登记豁免并写明理由（强制留痕）。
"""
from __future__ import annotations

from django.apps import apps as django_apps
from django.test import TestCase

from apps.tenants.managers import TenantManager

# 显式豁免：(app_label, model_name) -> 理由。
# 通过父 FK 间接隔离、或本身就是租户表的模型，不需要自带 TenantManager。
KNOWN_NON_SCOPED_EXEMPTIONS = {
    ('tenants', 'Tenant'): '租户表本身，不按 tenant 过滤',
    ('tenants', 'Membership'): '租户成员关系，按 user/tenant 直接查',
    ('accounts', 'AccountApplication'): '审批表，tenant 在通过时回写，列表仅超管可见',
    ('audit', 'OperationLog'): '跨租户审计日志，经审计接口按 superuser/tenant_admin 访问范围过滤，不参与业务租户隔离',
    ('accounts', 'Role'): '租户级角色，CRUD 在 employee_views 里按 request.tenant 过滤',
    ('resources', 'ScrollingTextItem'): '经 scrolling_text 父 FK 间接隔离',
    ('resources', 'TaskCommandStep'): '经 task_command 父 FK 间接隔离',
    ('ai_models', 'ChatMessage'): '经 conversation 父 FK 间接隔离',
    ('resources', 'TenantVideoQuota'): '租户级视频配额单例，经资源接口按 tenant 读写，不参与业务租户隔离',
}


def _model_has_tenant_fk(model) -> bool:
    return any(getattr(f, 'name', None) == 'tenant' for f in model._meta.get_fields())


class TenantIsolationContractTests(TestCase):
    def test_every_tenant_scoped_model_uses_tenant_manager(self):
        """每个带 tenant 外键的模型，默认 manager 必须是 TenantManager（除非显式豁免）。"""
        offenders = []
        for model in django_apps.get_models():
            label = (model._meta.app_label, model.__name__)
            if not _model_has_tenant_fk(model):
                continue
            if label in KNOWN_NON_SCOPED_EXEMPTIONS:
                continue
            if not isinstance(model._default_manager, TenantManager):
                offenders.append(
                    f'{label[0]}.{label[1]} 有 tenant 外键但默认 manager 不是 TenantManager '
                    f'(实际: {type(model._default_manager).__name__})。'
                    f'请加 `objects = TenantManager()`，或在 KNOWN_NON_SCOPED_EXEMPTIONS 登记豁免并写明理由。'
                )
        self.assertEqual(offenders, [], '\n' + '\n'.join(offenders))

    def test_exemptions_are_still_real_models(self):
        """豁免名单不能腐烂：登记的模型若被删/改名，强制清理名单。"""
        stale = []
        for (app_label, model_name) in KNOWN_NON_SCOPED_EXEMPTIONS:
            try:
                django_apps.get_model(app_label, model_name)
            except LookupError:
                stale.append(f'{app_label}.{model_name}')
        self.assertEqual(stale, [], f'豁免名单中的模型已不存在，请清理：{stale}')

    def test_llm_platform_models_and_tenant_settings_keep_expected_scope(self):
        """LLM 供应商是平台级；公司授权与默认设置必须按 tenant 隔离。"""
        provider = django_apps.get_model('ai_models', 'LLMProvider')
        grant = django_apps.get_model('ai_models', 'TenantLLMModelGrant')
        settings = django_apps.get_model('ai_models', 'TenantLLMSettings')

        self.assertFalse(_model_has_tenant_fk(provider))
        self.assertIsInstance(grant._default_manager, TenantManager)
        self.assertIsInstance(settings._default_manager, TenantManager)

    def test_for_tenant_none_returns_empty(self):
        """TenantManager.for_tenant(None) 必须返回空集（fail-closed，杜绝裸查泄漏）。"""
        from apps.devices.models import Device
        self.assertEqual(Device.objects.for_tenant(None).count(), 0)
