from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0031_rich_annotation_reply_blocks'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThirdPartyChatbotProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='供应商名称')),
                (
                    'provider_type',
                    models.CharField(
                        choices=[('ihuapeng_chatbot', '华鹏会话机器人')],
                        default='ihuapeng_chatbot',
                        max_length=64,
                        verbose_name='供应商类型',
                    ),
                ),
                ('api_base_url', models.URLField(max_length=512, verbose_name='API 地址')),
                ('api_key', models.CharField(max_length=512, verbose_name='应用密钥')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '第三方会话机器人供应商',
                'verbose_name_plural': '第三方会话机器人供应商',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ThirdPartyChatbotApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='机器人名称')),
                ('external_application_id', models.CharField(max_length=128, verbose_name='第三方应用 ID')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='机器人说明')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='chatbots',
                        to='ai_models.thirdpartychatbotprovider',
                        verbose_name='所属供应商',
                    ),
                ),
            ],
            options={
                'verbose_name': '第三方会话机器人',
                'verbose_name_plural': '第三方会话机器人',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TenantThirdPartyChatbotGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'chatbot',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tenant_grants',
                        to='ai_models.thirdpartychatbotapplication',
                        verbose_name='授权机器人',
                    ),
                ),
                (
                    'tenant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='third_party_chatbot_grants',
                        to='tenants.tenant',
                        verbose_name='所属公司',
                    ),
                ),
            ],
            options={
                'verbose_name': '公司第三方会话机器人授权',
                'verbose_name_plural': '公司第三方会话机器人授权',
            },
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='runtime_backend_type',
            field=models.CharField(
                choices=[('platform_llm', '平台 LLM'), ('third_party_chatbot', '第三方会话机器人')],
                default='platform_llm',
                max_length=32,
                verbose_name='运行后端',
            ),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='third_party_chatbot',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='agent_applications',
                to='ai_models.thirdpartychatbotapplication',
                verbose_name='第三方会话机器人',
            ),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='runtime_backend_type',
            field=models.CharField(
                choices=[('platform_llm', '平台 LLM'), ('third_party_chatbot', '第三方会话机器人')],
                default='platform_llm',
                max_length=32,
                verbose_name='运行后端',
            ),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='third_party_chatbot',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='conversations',
                to='ai_models.thirdpartychatbotapplication',
                verbose_name='第三方会话机器人',
            ),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='external_session',
            field=models.JSONField(blank=True, default=dict, verbose_name='外部会话状态'),
        ),
        migrations.AddConstraint(
            model_name='thirdpartychatbotapplication',
            constraint=models.UniqueConstraint(
                fields=('provider', 'external_application_id'),
                name='uniq_third_party_chatbot_provider_external_app',
            ),
        ),
        migrations.AddConstraint(
            model_name='tenantthirdpartychatbotgrant',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'chatbot'),
                name='uniq_tenant_third_party_chatbot_grant',
            ),
        ),
    ]
