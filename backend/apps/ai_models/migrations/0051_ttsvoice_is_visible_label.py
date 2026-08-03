from django.db import migrations, models


class Migration(migrations.Migration):
    """Relabel ``is_visible`` as 平台上架 (platform listing).

    Label-only: the field is platform-global and never meant a per-company
    visibility, which the 「公司可见」 wording wrongly suggested. No data change.
    """

    dependencies = [
        ('ai_models', '0050_ttsvoice_owner_tenant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ttsvoice',
            name='is_visible',
            field=models.BooleanField(default=True, verbose_name='平台上架'),
        ),
    ]
