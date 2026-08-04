import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Checkbox, Collapse, Empty, Segmented, Select, Space, Spin, Switch, Tag, Typography, message } from 'antd';
import { IconCloud, IconDeviceFloppy, IconHeadphones, IconRefresh, IconVolume } from '@tabler/icons-react';
import {
  fetchTenantTtsCardAuthorization,
  updateTenantTtsCardAuthorization,
  type TenantTtsCardAuthorization,
  type TenantTtsCardAuthorizationResponse,
  type TenantTtsCardAuthorizationVoice,
  type TenantTtsGrantMode,
} from '../../api/modules/tts';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';


/** A voice the platform has shelved cannot be authorized in either mode. */
const isShelved = (voice: TenantTtsCardAuthorizationVoice) => voice.isActive && voice.isVisible;

/** Voices this card would hand to the company if the pending edits were saved. */
const pendingAuthorizedVoices = (card: TenantTtsCardAuthorization) => {
  if (!card.grantIsActive || !card.isActive) return [];
  return card.voices.filter(
    (voice) => isShelved(voice) && (card.grantMode === 'all' || voice.voiceGrantIsActive),
  );
};

export const TtsCardAuthorizationPage = () => {
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [authorization, setAuthorization] = useState<TenantTtsCardAuthorizationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const activeTenants = useMemo(() => tenants.filter((tenant) => tenant.isActive), [tenants]);

  const loadTenants = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTenants({ page_size: 1000, include_hidden: true });
      setTenants(data.results);
      const firstActive = data.results.find((tenant) => tenant.isActive);
      setSelectedTenantId((current) => {
        const stillActive = data.results.some((tenant) => tenant.id === current && tenant.isActive);
        return stillActive ? current : firstActive?.id ?? null;
      });
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAuthorization = useCallback(async () => {
    if (!selectedTenantId) {
      setAuthorization(null);
      return;
    }
    setAuthLoading(true);
    try {
      setAuthorization(await fetchTenantTtsCardAuthorization(selectedTenantId));
    } finally {
      setAuthLoading(false);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  useEffect(() => {
    void loadAuthorization();
  }, [loadAuthorization]);

  // Mirrors the backend's post-save derivation, so the default voice offered here
  // is one the same PUT will actually accept.
  const authorizedVoiceOptions = useMemo(() => {
    if (!authorization) return [];
    return authorization.providers
      .map((card) => ({
        label: card.name,
        options: pendingAuthorizedVoices(card).map((voice) => ({
          label: `${voice.displayName} (${voice.voiceCode})`,
          value: voice.id,
        })),
      }))
      .filter((group) => group.options.length > 0);
  }, [authorization]);

  /**
   * Apply one local card edit and drop the default voice if that edit would
   * revoke it — the backend refuses a save that authorizes a card while making an
   * un-ticked voice the default, so the page must not build that payload.
   */
  const patchCard = (providerId: number, patch: (card: TenantTtsCardAuthorization) => TenantTtsCardAuthorization) => {
    if (!authorization) return;
    const providers = authorization.providers.map((item) => (item.id === providerId ? patch(item) : item));
    const stillAuthorized = providers.some((card) =>
      pendingAuthorizedVoices(card).some((voice) => voice.id === authorization.defaultVoiceId),
    );
    setAuthorization({
      ...authorization,
      defaultVoiceId: stillAuthorized ? authorization.defaultVoiceId : null,
      providers,
    });
  };

  const toggleGrant = (providerId: number, isActive: boolean) => {
    if (!authorization) return;
    patchCard(providerId, (item) => ({ ...item, grantIsActive: isActive }));
  };

  const setGrantMode = (providerId: number, grantMode: TenantTtsGrantMode) => {
    patchCard(providerId, (item) => ({ ...item, grantMode }));
  };

  const toggleVoiceGrant = (providerId: number, voice: TenantTtsCardAuthorizationVoice, checked: boolean) => {
    patchCard(providerId, (item) => ({
      ...item,
      voices: item.voices.map((row) => (row.id === voice.id ? { ...row, voiceGrantIsActive: checked } : row)),
    }));
  };

  const saveAuthorization = async () => {
    if (!authorization || !selectedTenantId) return;
    setSaving(true);
    try {
      const data = await updateTenantTtsCardAuthorization(selectedTenantId, {
        cardGrants: authorization.providers.map((card) => ({
          providerId: card.id,
          isActive: card.grantIsActive,
          grantMode: card.grantMode,
          // Only `selected` consumes the ticks; sending them in `all` mode would
          // be ignored by the backend anyway.
          ...(card.grantMode === 'selected'
            ? { voiceIds: card.voices.filter((voice) => voice.voiceGrantIsActive).map((voice) => voice.id) }
            : {}),
        })),
        defaultVoiceId: authorization.defaultVoiceId,
      });
      setAuthorization(data);
      message.success('TTS 卡片授权已保存');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <div className="space-y-5">
        <div className="page-hero">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
                <IconVolume size={22} />
              </div>
              <div>
                <Typography.Title level={3} className="m-0 text-lg tracking-normal text-slate-900">
                  公司 TTS 卡片授权
                </Typography.Title>
                <div className="mt-1 text-xs text-slate-500">
                  按公司分配可用的 TTS 卡片；卡片可整张授权，也可只授权其中指定的音色。
                </div>
              </div>
            </div>
            <Button icon={<IconRefresh size={16} />} className="rounded-md" loading={authLoading} onClick={() => void loadAuthorization()}>
              刷新
            </Button>
          </div>
        </div>

        <div className="bg-slate-50/50 border border-slate-100/80 rounded-xl p-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
            <span className="text-sm font-semibold text-slate-700 shrink-0">授权目标公司:</span>
            <Select
              showSearch
              className="w-full sm:w-[280px]"
              placeholder="请选择公司"
              value={selectedTenantId ?? undefined}
              optionFilterProp="label"
              options={activeTenants.map((tenant) => ({ label: tenant.name, value: tenant.id }))}
              onChange={setSelectedTenantId}
              size="large"
            />
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
            <span className="text-sm font-semibold text-slate-700 shrink-0">公司默认音色:</span>
            <Select
              className="w-full sm:w-[300px]"
              placeholder="暂无默认音色"
              allowClear
              showSearch
              optionFilterProp="label"
              value={authorization?.defaultVoiceId ?? undefined}
              options={authorizedVoiceOptions}
              onChange={(value) => authorization && setAuthorization({ ...authorization, defaultVoiceId: value ?? null })}
              size="large"
            />
            <Button
              type="primary"
              icon={<IconDeviceFloppy size={16} />}
              loading={saving}
              disabled={!authorization}
              onClick={() => void saveAuthorization()}
              size="large"
              className="w-full sm:w-auto bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-lg font-medium"
            >
              保存授权
            </Button>
          </div>
        </div>

        <Spin spinning={authLoading}>
          {authorization && authorization.providers.length === 0 ? (
            <Card className="rounded-xl border border-slate-100 shadow-card">
              <Empty description="暂无可分配的 TTS 卡片" />
            </Card>
          ) : (
            <Collapse
              className="custom-collapse border-slate-100 rounded-xl overflow-hidden shadow-sm bg-white"
              items={(authorization?.providers || []).map((card) => {
                const authorizedCount = pendingAuthorizedVoices(card).length;
                return {
                key: card.id,
                label: (
                  <div className="flex items-center justify-between w-full pr-4">
                    <Space size="middle" className="flex-wrap">
                      <IconCloud className="text-brand-600 text-base" />
                      <span className="font-semibold text-slate-800 text-sm">{card.name}</span>
                      <Tag color={card.isActive ? 'success' : 'default'} className="px-2 py-0.5 rounded-md border-0 text-xs">
                        {card.isActive ? '平台启用' : '平台停用'}
                      </Tag>
                      <Tag color={card.grantIsActive ? 'blue' : 'default'} className="px-2 py-0.5 rounded-md border-0 text-xs">
                        {card.grantIsActive ? '已授权' : '未授权'}
                      </Tag>
                      {card.supportedChannels?.includes('realtime') ? (
                        <Tag className="px-2 py-0.5 rounded-md border-0 text-xs">支持实时</Tag>
                      ) : null}
                    </Space>
                    <div className="flex items-center gap-3 shrink-0 ml-2" onClick={(event) => event.stopPropagation()}>
                      <span className="text-xs text-slate-400 font-medium">
                        已授权 {authorizedCount} / 共 {card.voices.length} 个音色
                      </span>
                      <Segmented
                        size="small"
                        value={card.grantMode}
                        disabled={!card.isActive || !card.grantIsActive}
                        options={[
                          { label: '全部音色', value: 'all' },
                          { label: '指定音色', value: 'selected' },
                        ]}
                        onChange={(value) => setGrantMode(card.id, value as TenantTtsGrantMode)}
                      />
                      <Switch
                        checked={card.grantIsActive}
                        disabled={!card.isActive}
                        onChange={(checked) => toggleGrant(card.id, checked)}
                        className="shadow-sm"
                      />
                    </div>
                  </div>
                ),
                children: (
                  <div className="divide-y divide-slate-100/80 px-2 bg-slate-50/20 rounded-lg">
                    {card.voices.length === 0 ? (
                      <div className="text-center py-6 text-slate-400 text-xs">该卡片下未录入任何音色</div>
                    ) : (
                      card.voices.map((voice) => (
                        <div key={voice.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-3 px-4">
                          <div className="flex items-center gap-3 min-w-0">
                            {card.grantMode === 'selected' ? (
                              <Checkbox
                                checked={voice.voiceGrantIsActive}
                                disabled={!card.grantIsActive || !card.isActive || !isShelved(voice)}
                                onChange={(event) => toggleVoiceGrant(card.id, voice, event.target.checked)}
                              />
                            ) : null}
                            <IconHeadphones size={16} className="text-slate-400 shrink-0" />
                            <div className="min-w-0">
                              <div className="font-semibold text-slate-800 text-sm truncate">{voice.displayName}</div>
                              <code className="text-[11px] font-mono text-slate-400 mt-0.5 block truncate">{voice.voiceCode}</code>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                            {voice.ownerTenant ? (
                              <Tag color="purple" className="m-0 px-2 py-0.5 rounded-md border-0 text-xs">
                                专属 · {voice.ownerTenant.name}
                              </Tag>
                            ) : null}
                            {voice.id === authorization?.defaultVoiceId ? (
                              <Tag color="success" className="m-0 px-2 py-0.5 rounded-md border-0 text-xs">公司默认</Tag>
                            ) : null}
                            <Tag
                              color={isShelved(voice) ? 'success' : 'default'}
                              className="m-0 px-2 py-0.5 rounded-md border-0 text-xs"
                            >
                              {isShelved(voice) ? '平台上架' : '平台下架'}
                            </Tag>
                            <Tag
                              color={voice.effectiveAuthorized ? 'blue' : 'default'}
                              className="m-0 px-2 py-0.5 rounded-md border-0 text-xs"
                            >
                              {voice.effectiveAuthorized ? '公司可用' : '公司不可用'}
                            </Tag>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ),
                };
              })}
            />
          )}
        </Spin>
      </div>
    </Spin>
  );
};
