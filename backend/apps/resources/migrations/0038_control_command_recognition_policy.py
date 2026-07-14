import decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0037_controlcommand_reply_strategy'),
    ]

    operations = [
        migrations.CreateModel(
            name='ControlCommandRecognitionPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direct_execution_threshold', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.90'), max_digits=3, verbose_name='直接执行阈值')),
                ('llm_confirmation_threshold', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.70'), max_digits=3, verbose_name='LLM 确认阈值')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('tenant', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='control_command_recognition_policy', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '控制指令识别策略',
                'verbose_name_plural': '控制指令识别策略',
            },
        ),
    ]
