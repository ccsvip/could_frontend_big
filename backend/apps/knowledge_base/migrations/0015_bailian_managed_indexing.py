from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge_base', '0014_knowledgebase_media_recall_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgebase',
            name='bailian_index_error',
            field=models.TextField(blank=True, default='', verbose_name='百炼索引错误'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='bailian_index_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='百炼 Index ID'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='bailian_index_job_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='百炼索引任务 ID'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='bailian_index_status',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='百炼索引状态'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='bailian_synced_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='百炼同步时间'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='parser',
            field=models.CharField(choices=[('AUTO_SELECT', '自动选择'), ('DOCMIND', '文档智能解析'), ('DOCMIND_DIGITAL', '电子文档解析'), ('DOCMIND_LLM_VERSION', '大模型文档解析')], default='AUTO_SELECT', max_length=32, verbose_name='百炼解析器'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='bailian_file_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='百炼 File ID'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='bailian_index_job_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='百炼索引任务 ID'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='bailian_parse_status',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='百炼解析状态'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='bailian_synced_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='百炼同步时间'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='content_md5',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='文件 MD5'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='sync_attempt',
            field=models.PositiveIntegerField(default=0, verbose_name='同步尝试次数'),
        ),
    ]
