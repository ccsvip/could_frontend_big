import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Give TTSVoice an owner company.

    ``null`` means a platform-public voice, which is what every existing row
    becomes — so no data backfill is needed and behaviour is unchanged.
    """

    dependencies = [
        ('ai_models', '0049_tts_voice_level_grants'),
        ('tenants', '0004_membership_role_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='ttsvoice',
            name='owner_tenant',
            field=models.ForeignKey(blank=True, help_text='留空表示平台公有音色；填写后只有该公司可用。', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='owned_tts_voices', to='tenants.tenant', verbose_name='归属公司'),
        ),
    ]
