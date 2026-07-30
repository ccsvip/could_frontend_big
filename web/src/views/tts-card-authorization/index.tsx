import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Collapse, Empty, Select, Space, Spin, Switch, Tag, Tooltip, Typography, message } from 'antd';
import { IconCloud, IconDeviceFloppy, IconHeadphones, IconRefresh, IconVolume } from '@tabler/icons-react';
import {
  fetchTenantTtsCardAuthorization,
  updateTenantTtsCardAuthorization,
  type TenantTtsCardAuthorization,
  type TenantTtsCardAuthorizationResponse,
} from '../../api/modules/tts';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';

const usageSummary = (usage: TenantTtsCardAuthorization['usage']) => {
  const parts: string[] = [];
  if (usage.tenantDefault) parts.push('公司默认音色');
  if (usage.deviceCount) parts.push(`设备 ${usage.deviceCount} 台`);
  if (usage.deviceApplicationCount) parts.push(`设备应用 ${usage.deviceApplicationCount} 个`);
  return parts.join(' · ');
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

  const authorizedVoiceOptions = useMemo(() => {
    if (!authorization) return [];
    return authorization.providers
      .filter((card) => card.grantIsActive)
      .map((card) => ({
        label: card.name,
        options: card.voices
          .filter((voice) => voice.isActive && voice.isVisible)
          .map((voice) => ({
            label: `${voice.displayName} (${voice.voiceCode})`,
            value: voice.id,
          })),
      }))
      .filter((group) => group.options.length > 0);
  }, [authorization]);

  const toggleGrant = (providerId: number, isActive: boolean) => {
    if (!authorization) return;
    const card = authorization.providers.find((item) => item.id === providerId);
    if (!isActive && card && !card.canDisableGrant) {
      message.warning(`${card.name} 仍在使用中（${usageSummary(card.usage)}），无法取消授权`);
      return;
    }
    const clearsDefault = !isActive && card?.voices.some((voice) => voice.id === authorization.defaultVoiceId);
    setAuthorization({
      ...authorization,
      defaultVoiceId: clearsDefault ? null : authorization.defaultVoiceId,
      providers: authorization.providers.map((item) =>
        item.id === providerId ? { ...item, grantIsActive: isActive } : item,
      ),
    });
  };

  const saveAuthorization = async () => {
    if (!authorization || !selectedTenantId) return;
    setSaving(true);
    try {
      const data = await updateTenantTtsCardAuthorization(selectedTenantId, {
        cardGrants: authorization.providers.map((card) => ({
          providerId: card.id,
          isActive: card.grantIsActive,
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
                  按公司分配可用的 TTS 卡片；公司只能看到并使用已授权卡片下的音色。
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

        <Alert
          type="info"
          showIcon
          message="卡片授权后，公司侧会自动看到该卡片下所有启用且展示的音色；MVP 不支持在卡片内排除单个音色。"
        />

        <Spin spinning={authLoading}>
          {authorization && authorization.providers.length === 0 ? (
            <Card className="rounded-xl border border-slate-100 shadow-card">
              <Empty description="暂无可分配的 TTS 卡片" />
            </Card>
          ) : (
            <Collapse
              className="custom-collapse border-slate-100 rounded-xl overflow-hidden shadow-sm bg-white"
              items={(authorization?.providers || []).map((card) => ({
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
                      {!card.canDisableGrant ? (
                        <span className="text-xs text-amber-600 font-medium">{usageSummary(card.usage)}</span>
                      ) : (
                        <span className="text-xs text-slate-400 font-medium">{card.voices.length} 个音色</span>
                      )}
                      <Tooltip title={card.canDisableGrant ? '' : `该卡片仍在使用中（${usageSummary(card.usage)}），无法取消授权`}>
                        <Switch
                          checked={card.grantIsActive}
                          disabled={!card.isActive || (card.grantIsActive && !card.canDisableGrant)}
                          onChange={(checked) => toggleGrant(card.id, checked)}
                          className="shadow-sm"
                        />
                      </Tooltip>
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
                            <IconHeadphones size={16} className="text-slate-400 shrink-0" />
                            <div className="min-w-0">
                              <div className="font-semibold text-slate-800 text-sm truncate">{voice.displayName}</div>
                              <code className="text-[11px] font-mono text-slate-400 mt-0.5 block truncate">{voice.voiceCode}</code>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                            {voice.id === authorization?.defaultVoiceId ? (
                              <Tag color="success" className="m-0 px-2 py-0.5 rounded-md border-0 text-xs">公司默认</Tag>
                            ) : null}
                            <Tag
                              color={voice.isActive && voice.isVisible ? 'success' : 'default'}
                              className="m-0 px-2 py-0.5 rounded-md border-0 text-xs"
                            >
                              {voice.isActive && voice.isVisible ? '全局可用' : '全局停用'}
                            </Tag>
                            <Tag
                              color={voice.effectiveAuthorized ? 'blue' : 'default'}
                              className="m-0 px-2 py-0.5 rounded-md border-0 text-xs"
                            >
                              {voice.effectiveAuthorized ? '公司可用' : '公司不可用'}
                            </Tag>
                            {usageSummary(voice.usage) ? (
                              <span className="text-[11px] text-slate-400">{usageSummary(voice.usage)}</span>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ),
              }))}
            />
          )}
        </Spin>
      </div>
    </Spin>
  );
};
