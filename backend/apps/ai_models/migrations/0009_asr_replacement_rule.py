from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0008_alter_asrconfig_options_alter_asrconfig_is_active_and_more'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ASRReplacementRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_text', models.CharField(max_length=128, verbose_name='原词')),
                ('replacement_text', models.CharField(max_length=128, verbose_name='替换词')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'tenant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='tenants.tenant',
                        verbose_name='所属公司',
                    ),
                ),
            ],
            options={
                'verbose_name': 'ASR 替换词',
                'verbose_name_plural': 'ASR 替换词',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='asrreplacementrule',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'source_text'),
                name='uniq_asr_replacement_rule_tenant_source',
            ),
        ),
    ]
