from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_base', '0012_knowledgebase_retrieval_min_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='description_embedding',
            field=models.JSONField(blank=True, default=list, verbose_name='说明文本向量'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='embedding_error',
            field=models.TextField(blank=True, default='', verbose_name='素材向量错误'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='embedding_model',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='素材向量模型'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='embedding_processed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='素材向量处理时间'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='embedding_status',
            field=models.CharField(
                choices=[
                    ('pending', '待处理'),
                    ('processing', '处理中'),
                    ('ready', '已就绪'),
                    ('failed', '处理失败'),
                ],
                default='pending',
                max_length=16,
                verbose_name='素材向量状态',
            ),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='multimodal_embedding',
            field=models.JSONField(blank=True, default=list, verbose_name='多模态向量'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='vlm_description',
            field=models.TextField(blank=True, default='', verbose_name='系统生成说明'),
        ),
        migrations.AddField(
            model_name='knowledgemediaasset',
            name='vlm_keywords',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='系统生成关键词'),
        ),
        migrations.AddIndex(
            model_name='knowledgemediaasset',
            index=models.Index(fields=['tenant', 'embedding_status'], name='kma_tenant_embed_status_idx'),
        ),
    ]
