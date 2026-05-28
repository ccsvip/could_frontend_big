from django.db import migrations, models
import django.db.models.deletion


def seed_chat_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    # Find AI parent menu
    ai_parent = Menu.objects.filter(key='/ai-models').first()
    if not ai_parent:
        return

    chat_menu, _ = Menu.objects.update_or_create(
        key='/ai-models/chat',
        defaults={
            'name': '聊天室',
            'path': '/ai-models/chat',
            'icon': 'MessageOutlined',
            'sort_order': 54,
            'is_active': True,
            'parent_id': ai_parent.id,
        },
    )

    permission_defs = [
        ('查看聊天', 'ai_models.chat.view', 'ai_models_chat', '允许查看聊天会话'),
        ('创建聊天', 'ai_models.chat.create', 'ai_models_chat', '允许创建聊天会话和发送消息'),
        ('删除聊天', 'ai_models.chat.delete', 'ai_models_chat', '允许删除聊天会话'),
    ]

    permission_points = []
    for name, code, module, description in permission_defs:
        pp, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': module,
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(pp)

    for role in Role.objects.all():
        role.menus.add(chat_menu)
        if role.code == 'admin':
            role.permission_points.add(*permission_points)
        else:
            # Non-admin: view + create (can chat but not delete others' conversations)
            readonly_pps = [p for p in permission_points if p.code in {'ai_models.chat.view', 'ai_models.chat.create'}]
            role.permission_points.add(*readonly_pps)


def unseed_chat_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    PermissionPoint.objects.filter(code__startswith='ai_models.chat.').delete()
    Menu.objects.filter(key='/ai-models/chat').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='新对话', max_length=256, verbose_name='会话标题')),
                ('model_name', models.CharField(blank=True, default='', max_length=128, verbose_name='模型名称')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('llm_provider', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='conversations',
                    to='ai_models.llmprovider',
                    verbose_name='LLM 供应商',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_conversations',
                    to='auth.user',
                    verbose_name='所属用户',
                )),
            ],
            options={
                'verbose_name': '聊天会话',
                'verbose_name_plural': '聊天会话',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('user', '用户'), ('assistant', '助手'), ('system', '系统')],
                    default='user', max_length=16, verbose_name='角色',
                )),
                ('content', models.TextField(verbose_name='消息内容')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='ai_models.chatconversation',
                    verbose_name='所属会话',
                )),
            ],
            options={
                'verbose_name': '聊天消息',
                'verbose_name_plural': '聊天消息',
                'ordering': ['created_at'],
            },
        ),
        migrations.RunPython(seed_chat_access_data, unseed_chat_access_data),
    ]
