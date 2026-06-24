import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0026_asr_vad_settings'),
        ('devices', '0011_deviceapplication_tts_voices'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceChatLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, default='', max_length=128, verbose_name='设备码')),
                ('source', models.CharField(choices=[('http', 'HTTP'), ('websocket', 'WebSocket')], max_length=32, verbose_name='来源')),
                ('question_text', models.TextField(verbose_name='问题')),
                ('answer_text', models.TextField(verbose_name='回答')),
                ('request_id', models.CharField(blank=True, default='', max_length=64, verbose_name='请求 ID')),
                ('trace_id', models.CharField(blank=True, default='', max_length=64, verbose_name='链路 ID')),
                ('model_name', models.CharField(blank=True, default='', max_length=128, verbose_name='模型名称')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('agent_application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='ai_models.agentapplication', verbose_name='绑定智能体快照')),
                ('application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='devices.deviceapplication')),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chat_logs', to='devices.device')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='tenants.tenant')),
            ],
            options={
                'verbose_name': '设备对话日志',
                'verbose_name_plural': '设备对话日志',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
