from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0023_control_command_value_type_ascii'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcommandstep',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='inner_tasks',
                to='resources.taskcommandstep',
                verbose_name='上级导航子任务',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='taskcommandstep',
            name='unique_task_command_step_order',
        ),
        migrations.AddConstraint(
            model_name='taskcommandstep',
            constraint=models.UniqueConstraint(
                condition=Q(('parent__isnull', True)),
                fields=('task_command', 'order'),
                name='unique_task_command_root_step_order',
            ),
        ),
        migrations.AddConstraint(
            model_name='taskcommandstep',
            constraint=models.UniqueConstraint(
                condition=Q(('parent__isnull', False)),
                fields=('parent', 'order'),
                name='unique_task_command_inner_step_order',
            ),
        ),
    ]
