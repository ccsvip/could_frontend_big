# Technical Design

## Root Cause

The canonical Aliyun/Qwen seed contains 48 voices. The current database also contains 54 legacy Loong-family rows that are absent from the repository and its Git history. Commit `ea290f5` changed company options from model-profile-filtered voices to every active, visible voice under an authorized card; commit `54d669d` renders that flat union directly in the company voice catalog. The change exposed the stale rows but did not create them.

## Data Cleanup

Add migration `0048_remove_legacy_loong_tts_voices.py`, depending on `0047_seed_cosyvoice_provider`.

The forward migration deletes only rows satisfying both:

- provider code equals `aliyun`;
- `voice_code` belongs to the explicit frozen set below.

```text
longanyang
longanhuan
longanhuan_v3
longhuhu_v3
longpaopao_v3
longjielidou_v3
longxian_v3
longling_v3
longshanshan_v3
longniuniu_v3
longjiaxin_v3
longjiayi_v3
longanyue_v3
longlaotie_v3
longshange_v3
longanmin_v3
loongkyong_v3
loongriko_v3
loongabby_v3
loongandy_v3
loongemily_v3
loongeric_v3
loongindah_v3
longfei_v3
longyingxiao_v3
longyingxun_v3
longyingjing_v3
longxiaochun_v3
longxiaoxia_v3
longmiao_v3
longsanshu_v3
longyuan_v3
longanran_v3
longanxuan_v3
longshuo_v3
longantai_v3
longhua_v3
longcheng_v3
longze_v3
longzhe_v3
longyan_v3
longxing_v3
longtian_v3
longwan_v3
longanrou_v3
longanzhi_v3
longanya_v3
longanqin_v3
longjiqi_v3
longhouge_v3
longdaiyu_v3
longlaobo_v3
longlaoyi_v3
loongbella_v3
```

Do not use a prefix delete. The reverse operation is a no-op because these rows are not canonical repository data and cannot be reconstructed from a trustworthy source.

Pre-change evidence: 54 matching rows, zero tenant-default references, zero device bindings, zero device-application references.

## Frontend Guard

Change the company catalog body to render `availableVoices`, matching the selector and count. This restores the pre-regression profile boundary without altering the provider-neutral API contract.

## Compatibility and Rollback

- Canonical 48 Aliyun/Qwen rows remain untouched.
- CosyVoice rows are protected by the provider-code predicate.
- Card grants and runtime contracts are unchanged.
- Code rollback does not recreate invalid rows. Database restoration, if ever required, must come from an operator-controlled backup rather than migration reverse logic.
