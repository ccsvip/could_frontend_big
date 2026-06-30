from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_base', '0011_knowledge_media_asset'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgebase',
            name='retrieval_min_score',
            field=models.FloatField(default=0.2, verbose_name='向量最低相关度'),
        ),
    ]
