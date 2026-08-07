from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0055_migrate_literal_tts_newline_filter'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='annotation_semantic_enabled',
            field=models.BooleanField(default=True, verbose_name='是否启用标注语义匹配'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='annotation_cosine_threshold',
            field=models.FloatField(default=0.88, verbose_name='标注语义余弦阈值'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='annotation_rerank_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用标注重排序（预留）'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='annotation_rerank_threshold',
            field=models.FloatField(default=0.0, verbose_name='标注重排序阈值（预留）'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='annotation_semantic_top_k',
            field=models.PositiveIntegerField(default=3, verbose_name='标注语义候选数（预留）'),
        ),
        migrations.CreateModel(
            name='AgentAnnotationEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding_fingerprint', models.CharField(max_length=128, verbose_name='嵌入指纹')),
                ('embedding_model_name', models.CharField(max_length=128, verbose_name='嵌入模型名')),
                ('dimensions', models.PositiveIntegerField(default=0, verbose_name='向量维度')),
                ('question_hash', models.CharField(max_length=64, verbose_name='问题哈希')),
                ('embedding', models.JSONField(blank=True, default=list, verbose_name='向量')),
                (
                    'status',
                    models.CharField(
                        choices=[('pending', '处理中'), ('ready', '就绪'), ('failed', '失败')],
                        default='pending',
                        max_length=16,
                        verbose_name='状态',
                    ),
                ),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('embedded_at', models.DateTimeField(blank=True, null=True, verbose_name='嵌入完成时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'annotation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='embeddings',
                        to='ai_models.agentannotation',
                        verbose_name='所属标注',
                    ),
                ),
                (
                    'application',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='annotation_embeddings',
                        to='ai_models.agentapplication',
                        verbose_name='所属智能体',
                    ),
                ),
                (
                    'tenant',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='tenants.tenant',
                        verbose_name='所属公司',
                    ),
                ),
            ],
            options={
                'verbose_name': '智能体标注向量',
                'verbose_name_plural': '智能体标注向量',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='agentannotationembedding',
            constraint=models.UniqueConstraint(
                fields=('annotation', 'embedding_fingerprint'),
                name='unique_agent_annotation_embedding_fingerprint',
            ),
        ),
        migrations.AddIndex(
            model_name='agentannotationembedding',
            index=models.Index(
                fields=['application', 'embedding_fingerprint', 'status'],
                name='ai_ann_emb_app_fp_st_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='agentannotationembedding',
            index=models.Index(
                fields=['tenant', 'embedding_fingerprint', 'status'],
                name='ai_ann_emb_tn_fp_st_idx',
            ),
        ),
    ]
