from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0020_scrolling_text_and_access_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcommandstep',
            name='image_text',
            field=models.TextField(blank=True, default='', verbose_name='图片子任务文本'),
        ),
    ]
