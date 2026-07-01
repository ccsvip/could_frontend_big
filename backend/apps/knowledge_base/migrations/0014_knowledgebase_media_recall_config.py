from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_base', '0013_knowledge_media_asset_multimodal_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgebase',
            name='media_max_assets',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='配套素材召回上限'),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='media_min_relevance',
            field=models.FloatField(default=0.22, verbose_name='配套素材最低相关度'),
        ),
    ]
