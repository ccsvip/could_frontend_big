from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0056_agent_annotation_semantic_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='annotation_match',
            field=models.JSONField(blank=True, default=dict, verbose_name='标注命中快照'),
        ),
    ]
