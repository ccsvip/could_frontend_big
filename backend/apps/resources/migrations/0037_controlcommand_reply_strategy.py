from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0036_controlcommand_execution_reply'),
    ]

    operations = [
        migrations.AddField(
            model_name='controlcommand',
            name='reply_strategy',
            field=models.CharField(
                choices=[('fixed', '固定回复'), ('generated', '智能生成')],
                default='fixed',
                max_length=16,
                verbose_name='未填写时回复方式',
            ),
        ),
    ]
