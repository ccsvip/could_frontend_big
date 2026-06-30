from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_base', '0010_ensure_index_fields_exist'),
        ('resources', '0032_remove_voice_tone_management_access'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeMediaAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource_type', models.CharField(max_length=20, verbose_name='素材类型')),
                ('resource_name', models.CharField(blank=True, default='', max_length=128, verbose_name='素材名称')),
                ('keywords', models.CharField(blank=True, default='', max_length=255, verbose_name='关键词')),
                ('description', models.CharField(blank=True, default='', max_length=500, verbose_name='说明')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('priority', models.IntegerField(default=0, verbose_name='优先级')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_knowledge_media_assets', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('knowledge_base', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media_assets', to='knowledge_base.knowledgebase', verbose_name='所属知识库')),
                ('resource', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='knowledge_media_assets', to='resources.resource', verbose_name='资源素材')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '知识库配套素材',
                'verbose_name_plural': '知识库配套素材',
                'ordering': ['-priority', '-updated_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='knowledgemediaasset',
            index=models.Index(fields=['tenant', 'knowledge_base'], name='kma_tenant_base_idx'),
        ),
        migrations.AddIndex(
            model_name='knowledgemediaasset',
            index=models.Index(fields=['knowledge_base', 'is_enabled'], name='kma_base_enabled_idx'),
        ),
        migrations.AddConstraint(
            model_name='knowledgemediaasset',
            constraint=models.UniqueConstraint(fields=('knowledge_base', 'resource'), name='uniq_knowledge_media_asset_base_resource'),
        ),
    ]
