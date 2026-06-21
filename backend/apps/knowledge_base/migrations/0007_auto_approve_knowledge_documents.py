from django.db import migrations, models


def approve_pending_documents(apps, schema_editor):
    KnowledgeDocument = apps.get_model('knowledge_base', 'KnowledgeDocument')
    KnowledgeDocument.objects.filter(processing_status='pending').update(processing_status='approved')


def restore_pending_default(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge_base', '0006_assign_knowledge_base_menu_to_tenants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='knowledgedocument',
            name='processing_status',
            field=models.CharField(
                choices=[('pending', '待审核'), ('approved', '已通过'), ('rejected', '已拒绝')],
                default='approved',
                max_length=20,
                verbose_name='处理状态',
            ),
        ),
        migrations.RunPython(approve_pending_documents, restore_pending_default),
    ]
