from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0025_knowledge_base_models_and_settings_menu'),
        ('devices', '0009_device_code_global_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceapplication',
            name='agent_application',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='device_applications',
                to='ai_models.agentapplication',
                verbose_name='绑定智能体',
            ),
        ),
    ]
