from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0033_resource_digital_human_background_and_image_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='storage_backend',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='对象存储后端'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='storage_backend',
            field=models.CharField(choices=[('local', '现有方案'), ('r2', 'R2 存储桶')], default='local', max_length=32, verbose_name='Active storage backend'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='r2_account_id',
            field=models.CharField(blank=True, default='', max_length=128, verbose_name='R2 Account ID'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='r2_access_key_id',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='R2 Access Key ID'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='r2_secret_access_key',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='R2 Secret Access Key'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='r2_bucket_name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='R2 Bucket'),
        ),
        migrations.AddField(
            model_name='minioconfig',
            name='r2_public_base_url',
            field=models.URLField(blank=True, default='', max_length=512, verbose_name='R2 Public base URL'),
        ),
    ]
