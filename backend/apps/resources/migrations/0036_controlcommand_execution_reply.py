from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0035_command_dispatch_execute_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlcommand',
            name='execution_reply',
            field=models.TextField(blank=True, default='', verbose_name='执行回复'),
        ),
    ]
