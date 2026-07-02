import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  IconApi,
  IconDatabase,
  IconReload,
  IconDeviceFloppy,
  IconCertificate,
} from '@tabler/icons-react';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import {
  fetchKnowledgeModelSettings,
  fetchTenantKnowledgeAuthorization,
  updateKnowledgeModelSettings,
  updateTenantKnowledgeAuthorization,
  type KnowledgeModelSettings,
  type TenantKnowledgeAuthorization,
} from '../../api/modules/knowledge-base';

type KnowledgeModelFormValues = {
  embeddingAlias: string;
  embeddingModel: string;
  embeddingBaseUrl: string;
  embeddingApiKey?: string;
  embeddingDimensions: number;
  embeddingIsActive: boolean;
  rerankAlias: string;
  rerankModel: string;
  rerankBaseUrl: string;
  rerankApiKey?: string;
  rerankIsActive: boolean;
};

const DEFAULT_MODEL_FORM: KnowledgeModelFormValues = {
  embeddingAlias: '',
  embeddingModel: 'text-embedding-v4',
  embeddingBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings',
  embeddingApiKey: '',
  embeddingDimensions: 0,
  embeddingIsActive: true,
  rerankAlias: '',
  rerankModel: 'qwen3-vl-rerank',
  rerankBaseUrl: 'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank',
  rerankApiKey: '',
  rerankIsActive: true,
};

const toModelFormValues = (settings: KnowledgeModelSettings): KnowledgeModelFormValues => ({
  embeddingAlias: settings.embedding.alias,
  embeddingModel: settings.embedding.model,
  embeddingBaseUrl: settings.embedding.baseUrl,
  embeddingApiKey: '',
  embeddingDimensions: settings.embedding.dimensions,
  embeddingIsActive: settings.embedding.isActive,
  rerankAlias: settings.rerank.alias,
  rerankModel: settings.rerank.model,
  rerankBaseUrl: settings.rerank.baseUrl,
  rerankApiKey: '',
  rerankIsActive: settings.rerank.isActive,
});

export const KnowledgeBaseSettingsPage = () => {
  const [settings, setSettings] = useState<KnowledgeModelSettings | null>(null);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [authorization, setAuthorization] = useState<TenantKnowledgeAuthorization | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingModels, setSavingModels] = useState(false);
  const [authorizationLoading, setAuthorizationLoading] = useState(false);
  const [savingAuthorization, setSavingAuthorization] = useState(false);
  const [modelForm] = Form.useForm<KnowledgeModelFormValues>();

  const activeTenants = useMemo(() => tenants.filter((tenant) => tenant.isActive), [tenants]);

  const loadPlatformData = useCallback(async () => {
    setLoading(true);
    try {
      const [nextSettings, tenantData] = await Promise.all([
        fetchKnowledgeModelSettings(),
        fetchTenants({ page_size: 1000, include_hidden: true }),
      ]);
      setSettings(nextSettings);
      setTenants(tenantData.results);
      modelForm.setFieldsValue(toModelFormValues(nextSettings));
      const nextActiveTenants = tenantData.results.filter((tenant) => tenant.isActive);
      if (!nextActiveTenants.some((tenant) => tenant.id === selectedTenantId)) {
        setSelectedTenantId(nextActiveTenants[0]?.id ?? null);
      }
    } finally {
      setLoading(false);
    }
  }, [modelForm, selectedTenantId]);

  const loadAuthorization = useCallback(async () => {
    if (!selectedTenantId) {
      setAuthorization(null);
      return;
    }
    setAuthorizationLoading(true);
    try {
      setAuthorization(await fetchTenantKnowledgeAuthorization(selectedTenantId));
    } finally {
      setAuthorizationLoading(false);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    void loadPlatformData();
  }, [loadPlatformData]);

  useEffect(() => {
    void loadAuthorization();
  }, [loadAuthorization]);

  const saveModelSettings = async () => {
    const values = await modelForm.validateFields();
    setSavingModels(true);
    try {
      const nextSettings = await updateKnowledgeModelSettings({
        embedding: {
          alias: values.embeddingAlias,
          model: values.embeddingModel,
          baseUrl: values.embeddingBaseUrl,
          apiKey: values.embeddingApiKey,
          dimensions: values.embeddingDimensions,
          isActive: values.embeddingIsActive,
        },
        rerank: {
          alias: values.rerankAlias,
          model: values.rerankModel,
          baseUrl: values.rerankBaseUrl,
          apiKey: values.rerankApiKey,
          isActive: values.rerankIsActive,
        },
      });
      setSettings(nextSettings);
      modelForm.setFieldsValue(toModelFormValues(nextSettings));
      message.success('知识库模型配置已保存');
      await loadAuthorization();
    } finally {
      setSavingModels(false);
    }
  };

  const toggleGrant = (modelType: 'embedding' | 'rerank', checked: boolean) => {
    if (!authorization) return;
    setAuthorization({
      ...authorization,
      embeddingModelId: modelType === 'embedding' ? (checked ? authorization.models.embedding.id : null) : authorization.embeddingModelId,
      rerankModelId: modelType === 'rerank' ? (checked ? authorization.models.rerank.id : null) : authorization.rerankModelId,
      models: {
        embedding: {
          ...authorization.models.embedding,
          grantIsActive: modelType === 'embedding' ? checked : authorization.models.embedding.grantIsActive,
        },
        rerank: {
          ...authorization.models.rerank,
          grantIsActive: modelType === 'rerank' ? checked : authorization.models.rerank.grantIsActive,
        },
      },
    });
  };

  const saveAuthorization = async () => {
    if (!authorization || !selectedTenantId) return;
    setSavingAuthorization(true);
    try {
      const nextAuthorization = await updateTenantKnowledgeAuthorization(selectedTenantId, {
        embeddingModelId: authorization.embeddingModelId,
        rerankModelId: authorization.rerankModelId,
        isActive: authorization.isActive,
      });
      setAuthorization(nextAuthorization);
      message.success('公司知识库授权已保存');
    } finally {
      setSavingAuthorization(false);
    }
  };

  const modelSettingsTab = (
    <Spin spinning={loading}>
      <Form form={modelForm} layout="vertical" initialValues={DEFAULT_MODEL_FORM}>
        <div className="grid gap-4 xl:grid-cols-2">
          <Card
            title={
              <Space>
                <IconDatabase className="text-brand-600" />
                <span>Embedding</span>
                <Tag color="geekblue">text-embedding-v4</Tag>
              </Space>
            }
            className="rounded-xl border-slate-100 shadow-sm"
          >
            <Form.Item name="embeddingAlias" label="公司侧别名" rules={[{ required: true, message: '请输入别名' }]}>
              <Input maxLength={128} />
            </Form.Item>
            <Form.Item name="embeddingModel" label="真实模型名称" rules={[{ required: true, message: '请输入真实模型名称' }]}>
              <Input maxLength={128} className="font-mono" />
            </Form.Item>
            <Form.Item name="embeddingBaseUrl" label="接口地址" rules={[{ required: true, message: '请输入接口地址' }]}>
              <Input />
            </Form.Item>
            <div className="grid gap-4 md:grid-cols-2">
              <Form.Item name="embeddingApiKey" label={`API Key${settings?.embedding.apiKeyConfigured ? ` (${settings.embedding.apiKeyMasked})` : ''}`}>
                <Input.Password placeholder={settings?.embedding.apiKeyConfigured ? '留空表示不修改' : undefined} />
              </Form.Item>
              <Form.Item name="embeddingDimensions" label="向量维度">
                <InputNumber min={0} className="w-full" />
              </Form.Item>
            </div>
            <Form.Item name="embeddingIsActive" label="平台启用" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </Card>
          <Card
            title={
              <Space>
                <IconCertificate className="text-brand-600" />
                <span>Rerank</span>
                <Tag color="purple">qwen3-vl-rerank</Tag>
              </Space>
            }
            className="rounded-xl border-slate-100 shadow-sm"
          >
            <Form.Item name="rerankAlias" label="公司侧别名" rules={[{ required: true, message: '请输入别名' }]}>
              <Input maxLength={128} />
            </Form.Item>
            <Form.Item name="rerankModel" label="真实模型名称" rules={[{ required: true, message: '请输入真实模型名称' }]}>
              <Input maxLength={128} className="font-mono" />
            </Form.Item>
            <Form.Item name="rerankBaseUrl" label="接口地址" rules={[{ required: true, message: '请输入接口地址' }]}>
              <Input />
            </Form.Item>
            <Form.Item name="rerankApiKey" label={`API Key${settings?.rerank.apiKeyConfigured ? ` (${settings.rerank.apiKeyMasked})` : ''}`}>
              <Input.Password placeholder={settings?.rerank.apiKeyConfigured ? '留空表示不修改' : undefined} />
            </Form.Item>
            <Form.Item name="rerankIsActive" label="平台启用" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </Card>
        </div>
        <div className="mt-4 flex justify-end">
          <Button type="primary" icon={<IconDeviceFloppy />} loading={savingModels} onClick={() => void saveModelSettings()}>
            保存模型配置
          </Button>
        </div>
      </Form>
    </Spin>
  );

  const authorizationTab = (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-4 lg:flex-row lg:items-center lg:justify-between">
        <Select
          showSearch
          className="w-full lg:w-[320px]"
          placeholder="请选择公司"
          value={selectedTenantId ?? undefined}
          optionFilterProp="label"
          options={activeTenants.map((tenant) => ({ label: tenant.name, value: tenant.id }))}
          onChange={setSelectedTenantId}
        />
        <Space>
          <Switch
            checked={authorization?.isActive ?? false}
            checkedChildren="启用"
            unCheckedChildren="停用"
            onChange={(checked) => authorization && setAuthorization({ ...authorization, isActive: checked })}
          />
          <Button type="primary" icon={<IconDeviceFloppy />} loading={savingAuthorization} onClick={() => void saveAuthorization()}>
            保存授权
          </Button>
        </Space>
      </div>
      <Spin spinning={authorizationLoading}>
        <div className="grid gap-4 xl:grid-cols-2">
          {authorization && (
            <>
              <Card className="rounded-xl border-slate-100 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-800">Embedding</div>
                    <div className="mt-1 text-sm text-slate-500">{authorization.models.embedding.alias}</div>
                  </div>
                  <Switch
                    checked={authorization.embeddingModelId === authorization.models.embedding.id}
                    disabled={!authorization.models.embedding.isActive}
                    onChange={(checked) => toggleGrant('embedding', checked)}
                  />
                </div>
              </Card>
              <Card className="rounded-xl border-slate-100 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-800">Rerank</div>
                    <div className="mt-1 text-sm text-slate-500">{authorization.models.rerank.alias}</div>
                  </div>
                  <Switch
                    checked={authorization.rerankModelId === authorization.models.rerank.id}
                    disabled={!authorization.models.rerank.isActive}
                    onChange={(checked) => toggleGrant('rerank', checked)}
                  />
                </div>
              </Card>
            </>
          )}
        </div>
      </Spin>
    </div>
  );

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="page-hero">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold text-slate-900">
              <IconApi className="text-brand-600" />
              <span>知识库设置</span>
            </h1>
            <Typography.Text className="text-sm text-slate-500">
              平台统一维护知识库检索模型与公司授权。
            </Typography.Text>
          </div>
          <Button icon={<IconReload />} onClick={() => void loadPlatformData()}>
            刷新
          </Button>
        </div>
      </div>
      <Card className="rounded-xl border-slate-100 shadow-sm">
        <Tabs
          items={[
            { key: 'models', label: '模型配置', children: modelSettingsTab },
            { key: 'authorization', label: '公司授权', children: authorizationTab },
          ]}
        />
      </Card>
    </div>
  );
};
