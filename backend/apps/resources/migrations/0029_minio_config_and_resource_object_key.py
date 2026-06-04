from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0028_commandgroup_tenant_controlcommand_tenant_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='object_key',
            field=models.CharField(blank=True, default='', max_length=512, verbose_name='MinIO 对象键'),
        ),
        migrations.CreateModel(
            name='MinioConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(blank=True, default='', help_text='host:port, e.g. localhost:9000', max_length=255, verbose_name='Endpoint')),
                ('access_key', models.CharField(blank=True, default='', max_length=255, verbose_name='Access Key')),
                ('secret_key', models.CharField(blank=True, default='', max_length=255, verbose_name='Secret Key')),
                ('bucket_name', models.CharField(blank=True, default='', max_length=255, verbose_name='Bucket')),
                ('secure', models.BooleanField(default=False, verbose_name='Use HTTPS')),
                ('region', models.CharField(blank=True, default='', max_length=64, verbose_name='Region')),
                ('public_base_url', models.URLField(blank=True, default='', max_length=512, verbose_name='Public base URL')),
                ('video_max_size_mb', models.PositiveIntegerField(default=1024, verbose_name='Video max size MB')),
                ('is_active', models.BooleanField(default=True, verbose_name='Enable video direct upload')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'MinIO 配置',
                'verbose_name_plural': 'MinIO 配置',
            },
        ),
    ]
