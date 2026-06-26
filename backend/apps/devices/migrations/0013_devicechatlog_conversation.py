import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_models', '0028_agent_application_publish_snapshot'),
        ('devices', '0012_devicechatlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicechatlog',
            name='conversation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='device_chat_logs',
                to='ai_models.chatconversation',
                verbose_name='智能体会话',
            ),
        ),
    ]
