from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_knowledge_base_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    knowledge_base_menu, _ = Menu.objects.update_or_create(
        key='/knowledge-base',
        defaults={
            'name': '知识库',
            'path': '/knowledge-base',
            'icon': 'CloudOutlined',
            'sort_order': 35,
            'is_active': True,
            'parent_id': None,
        },
    )

    permission_points = []
    for name, code, description in [
        ('查看知识库', 'knowledge_base.view', '允许查看知识库列表与详情'),
        ('上传知识库文档', 'knowledge_base.upload', '允许上传知识库文档'),
        ('下载知识库文档', 'knowledge_base.download', '允许下载单个知识库文档'),
        ('批量下载知识库文档', 'knowledge_base.bulk_download', '允许批量下载知识库文档'),
    ]:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': 'knowledge_base',
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(permission_point)

    for role in Role.objects.all():
        role.menus.add(knowledge_base_menu)
        role.permission_points.add(*permission_points)


def unseed_knowledge_base_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='knowledge_base.').delete()
    Menu.objects.filter(key='/knowledge-base').delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('accounts', '0004_menu_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='文档标题')),
                ('file', models.FileField(upload_to='knowledge-base/%Y/%m/%d', verbose_name='文档文件')),
                ('file_name', models.CharField(blank=True, default='', max_length=255, verbose_name='原始文件名')),
                ('file_extension', models.CharField(blank=True, default='', max_length=32, verbose_name='文件扩展名')),
                ('file_size', models.BigIntegerField(blank=True, null=True, verbose_name='文件大小(字节)')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='文档说明')),
                ('processing_status', models.CharField(choices=[('pending', '待审核'), ('approved', '已通过'), ('rejected', '已拒绝')], default='pending', max_length=20, verbose_name='处理状态')),
                ('processing_result', models.TextField(blank=True, default='', verbose_name='处理结果')),
                ('download_count', models.PositiveIntegerField(default=0, verbose_name='下载次数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='knowledge_documents', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
            ],
            options={
                'verbose_name': '知识库文档',
                'verbose_name_plural': '知识库文档',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.RunPython(seed_knowledge_base_access_data, unseed_knowledge_base_access_data),
    ]

