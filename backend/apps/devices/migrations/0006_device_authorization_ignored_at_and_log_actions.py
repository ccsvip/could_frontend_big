from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0005_deviceapplication_scrolling_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='authorization_ignored_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='授权请求忽略时间'),
        ),
        migrations.AlterField(
            model_name='deviceauthlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('activate', '激活'),
                    ('heartbeat', '心跳'),
                    ('config', '配置拉取'),
                    ('bind', '绑定'),
                    ('ignore', '忽略'),
                    ('authorize', '再次授权'),
                    ('revoke', '撤销授权'),
                ],
                max_length=32,
                verbose_name='动作',
            ),
        ),
    ]
