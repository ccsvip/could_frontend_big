from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0027_asr_filter_filler_words'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='published_config',
            field=models.JSONField(blank=True, default=dict, verbose_name='已发布配置'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='发布时间'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='published_version',
            field=models.PositiveIntegerField(default=0, verbose_name='发布版本'),
        ),
    ]
