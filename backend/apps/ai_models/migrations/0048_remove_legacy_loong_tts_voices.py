from django.db import migrations


LEGACY_ALIYUN_VOICE_CODES = (
    'longanyang',
    'longanhuan',
    'longanhuan_v3',
    'longhuhu_v3',
    'longpaopao_v3',
    'longjielidou_v3',
    'longxian_v3',
    'longling_v3',
    'longshanshan_v3',
    'longniuniu_v3',
    'longjiaxin_v3',
    'longjiayi_v3',
    'longanyue_v3',
    'longlaotie_v3',
    'longshange_v3',
    'longanmin_v3',
    'loongkyong_v3',
    'loongriko_v3',
    'loongabby_v3',
    'loongandy_v3',
    'loongemily_v3',
    'loongeric_v3',
    'loongindah_v3',
    'longfei_v3',
    'longyingxiao_v3',
    'longyingxun_v3',
    'longyingjing_v3',
    'longxiaochun_v3',
    'longxiaoxia_v3',
    'longmiao_v3',
    'longsanshu_v3',
    'longyuan_v3',
    'longanran_v3',
    'longanxuan_v3',
    'longshuo_v3',
    'longantai_v3',
    'longhua_v3',
    'longcheng_v3',
    'longze_v3',
    'longzhe_v3',
    'longyan_v3',
    'longxing_v3',
    'longtian_v3',
    'longwan_v3',
    'longanrou_v3',
    'longanzhi_v3',
    'longanya_v3',
    'longanqin_v3',
    'longjiqi_v3',
    'longhouge_v3',
    'longdaiyu_v3',
    'longlaobo_v3',
    'longlaoyi_v3',
    'loongbella_v3',
)


def remove_legacy_loong_voices(apps, schema_editor):
    TTSVoice = apps.get_model('ai_models', 'TTSVoice')
    TTSVoice.objects.filter(
        provider__code='aliyun',
        voice_code__in=LEGACY_ALIYUN_VOICE_CODES,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0047_seed_cosyvoice_provider'),
    ]

    operations = [
        migrations.RunPython(remove_legacy_loong_voices, migrations.RunPython.noop),
    ]
