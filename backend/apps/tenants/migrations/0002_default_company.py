from django.db import migrations


DEFAULT_TENANT_CODE = 'default'
DEFAULT_TENANT_NAME = '默认公司'


def create_default_company(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Membership = apps.get_model('tenants', 'Membership')
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    User = apps.get_model('auth', 'User')

    tenant, _ = Tenant.objects.get_or_create(
        code=DEFAULT_TENANT_CODE,
        defaults={'name': DEFAULT_TENANT_NAME, 'is_legacy': True, 'is_active': True},
    )

    # 默认公司分到全量目录，保证历史用户改造后可见范围与改造前一致。
    tenant.menus.set(Menu.objects.all())
    tenant.permission_points.set(PermissionPoint.objects.all())

    # 所有非 superuser 用户收容进默认公司；superuser 视为平台运维，不建 Membership。
    for user in User.objects.filter(is_superuser=False):
        Membership.objects.get_or_create(
            user=user,
            defaults={'tenant': tenant, 'is_tenant_admin': False},
        )


def remove_default_company(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Membership = apps.get_model('tenants', 'Membership')

    tenant = Tenant.objects.filter(code=DEFAULT_TENANT_CODE).first()
    if tenant is None:
        return
    Membership.objects.filter(tenant=tenant).delete()
    tenant.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('accounts', '0007_accountuser'),
        # 钉住各 app 最后一条迁移，确保全部菜单/权限点 seed 完成后再回填默认公司，
        # 否则 Menu.objects.all() 可能只抓到部分目录。
        ('devices', '0001_initial'),
        ('resources', '0027_point_is_show'),
        ('knowledge_base', '0002_access_data'),
        ('ai_models', '0005_chat_summary_message_feedback'),
    ]

    operations = [
        migrations.RunPython(create_default_company, remove_default_company),
    ]
