from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0026_remove_cross_tenant_wake_word_bindings'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicechatlog',
            name='annotation_match',
            field=models.JSONField(blank=True, default=dict, verbose_name='标注命中快照'),
        ),
    ]
