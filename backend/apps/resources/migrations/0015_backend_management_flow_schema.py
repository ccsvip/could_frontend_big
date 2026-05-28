from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0014_command_types_menu_tree'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommandGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='指令管理名称')),
                (
                    'group_type',
                    models.CharField(
                        choices=[('control', '控制指令'), ('task', '任务指令')],
                        max_length=20,
                        verbose_name='指令类型',
                    ),
                ),
                ('export_enabled', models.BooleanField(default=False, verbose_name='是否允许导出')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '指令分组',
                'verbose_name_plural': '指令分组',
                'ordering': ['group_type', 'name', 'id'],
            },
        ),
        migrations.DeleteModel(name='PointWorkflowStep'),
        migrations.DeleteModel(name='PointResource'),
        migrations.DeleteModel(name='NavigationCommand'),
        migrations.RenameField(
            model_name='point',
            old_name='lookup_key',
            new_name='command',
        ),
        migrations.RemoveField(model_name='point', name='description'),
        migrations.AlterField(
            model_name='point',
            name='command',
            field=models.CharField(max_length=128, unique=True, verbose_name='点位命令'),
        ),
        migrations.AlterField(
            model_name='point',
            name='name',
            field=models.CharField(max_length=128, verbose_name='点位名称'),
        ),
        migrations.AlterField(
            model_name='point',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否启用'),
        ),
        migrations.AlterModelOptions(
            name='point',
            options={'ordering': ['command', 'id'], 'verbose_name': '点位管理', 'verbose_name_plural': '点位管理'},
        ),
        migrations.RemoveField(model_name='controlcommand', name='category'),
        migrations.RemoveField(model_name='controlcommand', name='target'),
        migrations.RemoveField(model_name='controlcommand', name='payload_json'),
        migrations.RemoveField(model_name='controlcommand', name='description'),
        migrations.RemoveField(model_name='controlcommand', name='sort'),
        migrations.RemoveField(model_name='controlcommand', name='is_visible'),
        migrations.AddField(
            model_name='controlcommand',
            name='group',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='control_commands',
                to='resources.commandgroup',
                verbose_name='所属指令分组',
            ),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='command_code',
            field=models.CharField(max_length=128, unique=True, verbose_name='指令'),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='host',
            field=models.GenericIPAddressField(verbose_name='IP'),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='name',
            field=models.CharField(max_length=128, verbose_name='名称'),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='port',
            field=models.PositiveIntegerField(verbose_name='端口'),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='protocol',
            field=models.CharField(
                choices=[('UDP', 'UDP'), ('TCP', 'TCP')],
                default='UDP',
                max_length=16,
                verbose_name='调用方式',
            ),
        ),
        migrations.AlterField(
            model_name='controlcommand',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否启用'),
        ),
        migrations.AlterModelOptions(
            name='controlcommand',
            options={'ordering': ['group__name', 'name', 'id'], 'verbose_name': '控制指令', 'verbose_name_plural': '控制指令'},
        ),
        migrations.CreateModel(
            name='TaskCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='名称')),
                ('command_code', models.CharField(max_length=128, unique=True, verbose_name='指令')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'group',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='task_commands',
                        to='resources.commandgroup',
                        verbose_name='所属指令分组',
                    ),
                ),
            ],
            options={
                'verbose_name': '任务指令',
                'verbose_name_plural': '任务指令',
                'ordering': ['group__name', 'name', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TaskCommandStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(verbose_name='顺序')),
                (
                    'task_type',
                    models.CharField(
                        choices=[
                            ('command', '指令'),
                            ('text', '文本'),
                            ('image', '图片'),
                            ('video', '视频'),
                            ('navigation', '导航指令'),
                        ],
                        max_length=20,
                        verbose_name='子任务类型',
                    ),
                ),
                ('text_content', models.TextField(blank=True, default='', verbose_name='文本内容')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'control_command',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='task_steps',
                        to='resources.controlcommand',
                        verbose_name='控制指令',
                    ),
                ),
                (
                    'point',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='task_steps',
                        to='resources.point',
                        verbose_name='点位',
                    ),
                ),
                (
                    'resource',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='task_steps',
                        to='resources.resource',
                        verbose_name='图片/视频资源',
                    ),
                ),
                (
                    'task_command',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tasks',
                        to='resources.taskcommand',
                        verbose_name='任务指令',
                    ),
                ),
            ],
            options={
                'verbose_name': '任务子任务',
                'verbose_name_plural': '任务子任务',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='taskcommandstep',
            constraint=models.UniqueConstraint(fields=('task_command', 'order'), name='unique_task_command_step_order'),
        ),
    ]
