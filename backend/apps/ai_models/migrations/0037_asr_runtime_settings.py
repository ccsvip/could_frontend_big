from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0036_asr_filler_word_set'),
    ]

    operations = [
        migrations.CreateModel(
            name='ASRRuntimeSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('effective_input_timeout_seconds', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='有效输入等待上限（秒）')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='asr_runtime_settings', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '公司 ASR 运行时设置',
                'verbose_name_plural': '公司 ASR 运行时设置',
            },
        ),
    ]
