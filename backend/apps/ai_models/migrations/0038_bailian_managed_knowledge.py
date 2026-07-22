from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0037_asr_runtime_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='BailianKnowledgeConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_key_id', models.CharField(blank=True, default='', max_length=256, verbose_name='AccessKey ID')),
                ('access_key_secret_encrypted', models.TextField(blank=True, default='', verbose_name='加密 AccessKey Secret')),
                ('workspace_id', models.CharField(blank=True, default='', max_length=128, verbose_name='百炼 Workspace ID')),
                ('category_id', models.CharField(default='default', max_length=128, verbose_name='百炼 Category ID')),
                ('endpoint', models.CharField(default='bailian.cn-beijing.aliyuncs.com', max_length=255, verbose_name='百炼 API 地址')),
                ('is_active', models.BooleanField(default=False, verbose_name='是否启用')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '百炼知识库配置',
                'verbose_name_plural': '百炼知识库配置',
            },
        ),
        migrations.AddField(
            model_name='tenantknowledgemodelsettings',
            name='managed_rag_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用百炼托管知识库'),
        ),
    ]
