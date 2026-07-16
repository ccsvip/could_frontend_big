from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0035_agent_application_tts_filter_exclude_patterns'),
    ]

    operations = [
        migrations.CreateModel(
            name='ASRFillerWordSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('words_text', models.TextField(blank=True, default='', verbose_name='语气词')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('tenant', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='asr_filler_word_set', to='tenants.tenant', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '公司 ASR 语气词词表',
                'verbose_name_plural': '公司 ASR 语气词词表',
            },
        ),
        migrations.RemoveField(
            model_name='asrconfig',
            name='filter_filler_words',
        ),
    ]
