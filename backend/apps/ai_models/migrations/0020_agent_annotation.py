from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0004_membership_role_name'),
        ('ai_models', '0019_drop_stale_agentapplication_max_tokens_unlimited'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentAnnotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=500, verbose_name='标准问题')),
                ('answer', models.TextField(verbose_name='标准回复')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('hit_count', models.PositiveIntegerField(default=0, verbose_name='命中次数')),
                ('last_hit_at', models.DateTimeField(blank=True, null=True, verbose_name='最近命中时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='ai_models.agentapplication', verbose_name='所属智能体')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_agent_annotations', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('source_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='annotation_sources', to='ai_models.chatmessage', verbose_name='来源助手消息')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '智能体标注',
                'verbose_name_plural': '智能体标注',
                'ordering': ['-updated_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='agentannotation',
            constraint=models.UniqueConstraint(fields=('application', 'question'), name='unique_agent_annotation_question_per_application'),
        ),
    ]
