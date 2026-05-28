# Generated migration for adding unique constraint to phone field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountapplication',
            name='phone',
            field=models.CharField(max_length=20, unique=True, verbose_name='手机号'),
        ),
    ]
