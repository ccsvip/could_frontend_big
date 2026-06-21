from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge_base', '0007_auto_approve_knowledge_documents'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='knowledgedocument',
            name='processing_result',
        ),
        migrations.RemoveField(
            model_name='knowledgedocument',
            name='processing_status',
        ),
    ]
