import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Empty, Space, Spin, Tag, Typography, message } from 'antd';
import { IconCircleCheck, IconFlask, IconReload } from '@tabler/icons-react';
import { useAuthStore } from '../../store/auth';
import {
  fetchCompanyLLMOptions,
  testCompanyLLMModel,
  updateCompanyDefaultLLMModel,
  type CompanyLLMOptions,
  type LLMModelOption,
} from '../../api/modules/llm-settings';

const getModelAlias = (model: LLMModelOption) => model.displayName || '未设置模型别称';

export const LlmSettingsPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canUpdate = hasPermission('ai_models.llm.update');
  const [options, setOptions] = useState<CompanyLLMOptions | null>(null);
  const [loading, setLoading] = useState(false);
  const [testingModelId, setTestingModelId] = useState<number | null>(null);
  const [savingModelId, setSavingModelId] = useState<number | null>(null);

  const loadOptions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCompanyLLMOptions();
      setOptions(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const availableModels = useMemo(
    () => options?.providers.flatMap((provider) => provider.models) ?? [],
    [options],
  );

  const defaultModel = useMemo(() => {
    if (!options?.defaultModelId) return null;
    return availableModels.find((item) => item.id === options.defaultModelId) || null;
  }, [availableModels, options?.defaultModelId]);

  const handleTest = async (model: LLMModelOption) => {
    setTestingModelId(model.id);
    try {
      const result = await testCompanyLLMModel(model.id);
      if (result.success) {
        message.success(`连接成功，耗时 ${result.latencyMs}ms`);
      } else {
        message.error(result.message);
      }
    } finally {
      setTestingModelId(null);
    }
  };

  const handleSetDefault = async (model: LLMModelOption) => {
    setSavingModelId(model.id);
    try {
      const data = await updateCompanyDefaultLLMModel(model.id);
      setOptions(data);
      message.success('默认模型已更新');
    } finally {
      setSavingModelId(null);
    }
  };

  const renderModel = (model: LLMModelOption) => (
    <div key={model.id} className="flex flex-col gap-3 border-t border-slate-100 py-4 first:border-t-0 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Typography.Text className="font-medium text-slate-900">{getModelAlias(model)}</Typography.Text>
          {model.isDefault && <Tag color="blue">默认</Tag>}
        </div>
      </div>
      <Space size="small">
        <Button
          icon={<IconFlask />}
          loading={testingModelId === model.id}
          onClick={() => void handleTest(model)}
        >
          测试
        </Button>
        {canUpdate && (
          <Button
            type={model.isDefault ? 'default' : 'primary'}
            disabled={model.isDefault}
            loading={savingModelId === model.id}
            onClick={() => void handleSetDefault(model)}
          >
            {model.isDefault ? '当前默认' : '设为默认'}
          </Button>
        )}
      </Space>
    </div>
  );

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Typography.Title level={3} className="!mb-1">LLM设置</Typography.Title>
          <Typography.Text type="secondary">查看公司可用模型、测试连通性，并维护默认模型。</Typography.Text>
        </div>
        <Button icon={<IconReload />} onClick={() => void loadOptions()}>
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            {availableModels.length ? (
              <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <Typography.Text className="font-semibold text-slate-900">可用模型</Typography.Text>
                  <Tag color="green">{availableModels.length} 个可用模型</Tag>
                </div>
                {availableModels.map((model) => renderModel(model))}
              </section>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-200 bg-white py-16">
                <Empty description="暂无可用模型，请联系管理员配置 LLM 设置" />
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <Space className="mb-3">
                <IconCircleCheck className="text-brand-500" />
                <Typography.Text className="font-semibold text-slate-900">当前默认模型</Typography.Text>
              </Space>
              {defaultModel ? (
                <Typography.Title level={5} className="!mb-0">
                  {getModelAlias(defaultModel)}
                </Typography.Title>
              ) : (
                <Typography.Text type="secondary">尚未设置默认模型</Typography.Text>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <Typography.Text className="font-semibold text-slate-900">测试设置</Typography.Text>
              <div className="mt-3 space-y-3 text-sm text-slate-600">
                <div className="rounded-md bg-slate-50 p-3 leading-relaxed">
                  {options?.testSettings.testPrompt || '暂无测试提示词'}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-md bg-slate-50 p-2">
                    <div className="font-semibold text-slate-900">{options?.testSettings.testCooldownSeconds ?? '-'}</div>
                    <div className="text-xs text-slate-400">冷却秒</div>
                  </div>
                  <div className="rounded-md bg-slate-50 p-2">
                    <div className="font-semibold text-slate-900">{options?.testSettings.testTimeoutSeconds ?? '-'}</div>
                    <div className="text-xs text-slate-400">超时秒</div>
                  </div>
                  <div className="rounded-md bg-slate-50 p-2">
                    <div className="font-semibold text-slate-900">{options?.testSettings.testMaxTokens ?? '-'}</div>
                    <div className="text-xs text-slate-400">Tokens</div>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </Spin>
    </div>
  );
};
