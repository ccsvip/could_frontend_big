import { useCallback, useEffect, useMemo, useState } from 'react';
import { Avatar, Button, Card, Input, Radio, Space, Spin, Tag, Typography, message } from 'antd';
import {
  CheckCircleOutlined,
  CustomerServiceOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  SoundOutlined,
} from '@ant-design/icons';
import {
  fetchCompanyTtsOptions,
  testCompanyTts,
  updateCompanyDefaultTtsVoice,
  type CompanyTtsOptions,
  type TtsVoiceRecord,
} from '../../api/modules/tts';

export const TtsManagementPage = () => {
  const [options, setOptions] = useState<CompanyTtsOptions | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testText, setTestText] = useState('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const setAudioBlob = useCallback((blob: Blob) => {
    setAudioUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(blob);
    });
  }, []);

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  const loadOptions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCompanyTtsOptions();
      setOptions(data);
      setSelectedVoiceId(data.defaultVoiceId);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const selectedVoice = useMemo(
    () => options?.voices.find((voice) => voice.id === selectedVoiceId) ?? null,
    [options?.voices, selectedVoiceId],
  );

  const defaultVoice = useMemo(
    () => options?.voices.find((voice) => voice.id === options.defaultVoiceId) ?? null,
    [options?.defaultVoiceId, options?.voices],
  );

  const saveDefaultVoice = async () => {
    if (!selectedVoiceId) {
      message.warning('请选择音色');
      return;
    }
    setSaving(true);
    try {
      const data = await updateCompanyDefaultTtsVoice(selectedVoiceId);
      setOptions(data);
      setSelectedVoiceId(data.defaultVoiceId);
      message.success('默认音色已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const blob = await testCompanyTts({ text: testText });
      setAudioBlob(blob);
      message.success('TTS 测试音频已生成');
    } finally {
      setTesting(false);
    }
  };

  const renderVoice = (voice: TtsVoiceRecord) => {
    const checked = selectedVoiceId === voice.id;
    return (
      <button
        key={voice.id}
        type="button"
        onClick={() => setSelectedVoiceId(voice.id)}
        className={`flex min-h-[112px] w-full items-center gap-4 rounded-xl border bg-white p-4 text-left transition duration-200 hover:border-brand-300 hover:shadow-card-hover ${
          checked ? 'border-brand-500 ring-2 ring-brand-100' : 'border-slate-200 shadow-card'
        }`}
      >
        <Avatar src={voice.avatarPath} icon={<CustomerServiceOutlined />} size={56} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900">{voice.displayName}</span>
            {voice.isDefault ? <Tag color="success" className="m-0 border-0 rounded-md px-2 py-0.5">当前默认</Tag> : null}
          </div>
          <div className="mt-1" onClick={(e) => e.stopPropagation()}>
            <Typography.Text
              copyable={{ text: voice.voiceCode }}
              className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded inline-block"
            >
              {voice.voiceCode}
            </Typography.Text>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {voice.gender === 'female' ? '女声' : voice.gender === 'male' ? '男声' : voice.gender || '-'}
          </div>
        </div>
        <Radio checked={checked} className="text-brand-600" />
      </button>
    );
  };

  return (
    <Spin spinning={loading}>
      <div className="space-y-5">
        <div className="page-hero">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
                <SoundOutlined className="text-xl" />
              </div>
              <div>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Typography.Title level={3} className="!m-0 !text-lg !tracking-normal !text-slate-900">
                    TTS 管理
                  </Typography.Title>
                  <Tag color={options?.provider.isActive ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {options?.provider.isActive ? '服务启用' : '服务停用'}
                  </Tag>
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  {options?.provider.name || '阿里云 TTS'} · {options?.sampleRate || 24000}Hz · PCM 单声道
                </div>
              </div>
            </div>
            <Space wrap>
              <Button icon={<ReloadOutlined />} className="rounded-md" loading={loading} onClick={() => void loadOptions()}>
                刷新
              </Button>
              <Button type="primary" icon={<SaveOutlined />} className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md" loading={saving} onClick={() => void saveDefaultVoice()}>
                保存默认音色
              </Button>
            </Space>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="space-y-4">
            <Card className="rounded-xl border border-slate-100 shadow-card">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <Avatar src={defaultVoice?.avatarPath} icon={<CustomerServiceOutlined />} size={48} />
                  <div>
                    <div className="text-sm font-semibold text-slate-900 mb-1">
                      {defaultVoice?.displayName || '未选择默认音色'}
                    </div>
                    {defaultVoice?.voiceCode ? (
                      <Typography.Text
                        copyable={{ text: defaultVoice.voiceCode }}
                        className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded cursor-pointer inline-block"
                      >
                        {defaultVoice.voiceCode}
                      </Typography.Text>
                    ) : (
                      <div className="text-xs text-slate-400">-</div>
                    )}
                  </div>
                </div>
                {selectedVoice ? (
                  <div className="flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-xs font-medium text-brand-700">
                    <CheckCircleOutlined />
                    <span>已选择 {selectedVoice.displayName}</span>
                  </div>
                ) : null}
              </div>
            </Card>

            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {(options?.voices ?? []).map(renderVoice)}
            </div>
          </div>

          <Card title="测试播放" className="rounded-xl border border-slate-100 shadow-card">
            <div className="space-y-4">
              <Input.TextArea
                rows={6}
                value={testText}
                maxLength={500}
                showCount
                onChange={(event) => setTestText(event.target.value)}
                placeholder={options?.defaultTestText || '留空时使用平台默认测试文本'}
                className="rounded-lg"
              />
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={testing}
                block
                className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md"
                onClick={() => void handleTest()}
              >
                生成测试音频
              </Button>
              {audioUrl ? (
                <audio controls src={audioUrl} className="w-full mt-2" />
              ) : (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-400">
                  暂无测试音频
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </Spin>
  );
};
