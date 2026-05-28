from django.db import migrations, models
import django.db.models.deletion


def block_existing_points_before_breaking_workflow_migration(apps, schema_editor):
    Point = apps.get_model('resources', 'Point')
    if Point.objects.exists():
        raise RuntimeError(
            'Point workflow migration blocked: existing Point rows must be reset/rebuilt with explicit '
            'operator approval before removing the legacy single-resource binding.'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('resources', '0011_navigationcommand_and_access_data'),
    ]

    operations = [
        migrations.RunPython(block_existing_points_before_breaking_workflow_migration, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='point',
            name='resource',
        ),
        migrations.CreateModel(
            name='PointWorkflowStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sort_order', models.PositiveIntegerField(verbose_name='步骤顺序')),
                ('wait_seconds', models.PositiveIntegerField(default=0, verbose_name='等待秒数')),
                ('auto_next', models.BooleanField(default=True, verbose_name='自动下一步')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflow_steps', to='resources.point', verbose_name='点位')),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='workflow_steps', to='resources.pointresource', verbose_name='点位资源')),
            ],
            options={
                'verbose_name': '点位流程步骤',
                'verbose_name_plural': '点位流程步骤',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='pointworkflowstep',
            constraint=models.UniqueConstraint(fields=('point', 'sort_order'), name='unique_point_workflow_step_order'),
        ),
        migrations.AddConstraint(
            model_name='pointworkflowstep',
            constraint=models.CheckConstraint(check=models.Q(('wait_seconds__lte', 3600)), name='point_step_wait_seconds_lte_3600'),
        ),
    ]
