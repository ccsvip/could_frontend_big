import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Collapse,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  IconApi,
  IconEdit,
  IconPlus,
  IconRefresh,
  IconRobot,
  IconTrash,
} from '@tabler/icons-react';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import {
  createPlatformThirdPartyChatbotIntegration,
  deletePlatformThirdPartyChatbotIntegration,
  fetchPlatformThirdPartyChatbotIntegrations,
  testPlatformThirdPartyChatbotIntegrationDraft,
  updatePlatformThirdPartyChatbotIntegration,
  type ThirdPartyChatbotApiStep,
  type ThirdPartyChatbotIntegrationConfig,
  type ThirdPartyChatbotIntegrationPayload,
  type ThirdPartyChatbotIntegrationRecord,
  type ThirdPartyChatbotIntegrationTestResult,
} from '../../api/modules/llm-settings';

type StepFormValue = Omit<ThirdPartyChatbotApiStep, 'body'> & {
  bodyText: string;
  stream?: boolean;
  hasStreamField?: boolean;
};

type SchemeTemplate = {
  key: 'scheme_a' | 'scheme_b';
  title: string;
  subtitle: string;
  createValues: () => IntegrationFormValues;
};

type IntegrationFormValues = Omit<ThirdPartyChatbotIntegrationPayload, 'config'> & {
  config: {
    steps: StepFormValue[];
    answerPaths: string[];
    streamingText?: string;
  };
  tenantIds: number[];
  testQuestion?: string;
};

const METHOD_OPTIONS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'].map((method) => ({
  label: method,
  value: method,
}));

const FLOWMESH_STREAMING_CONFIG = {
  enabled: true,
  sessionStep: {
    key: 'create_session',
    name: '创建会话',
    method: 'POST',
    path: '/apps/{{externalApplicationId}}/sessions',
    headers: [
      { key: 'Authorization', value: 'Bearer {{apiKey}}' },
      { key: 'Accept', value: 'application/json' },
      { key: 'Content-Type', value: 'application/json' },
    ],
    body: {},
    extract: [{ name: 'sessionId', path: '$.data.sessionId' }],
    success: { httpStatus: '200-299', bodyPath: '$.code', equals: 1 },
    errorMessagePath: '$.message',
  },
  messageStep: {
    key: 'stream_message',
    name: '流式发送消息',
    method: 'POST',
    path: '/apps/{{externalApplicationId}}/sessions/{{sessionId}}/chat',
    headers: [
      { key: 'Authorization', value: 'Bearer {{apiKey}}' },
      { key: 'Accept', value: 'text/event-stream' },
      { key: 'Content-Type', value: 'application/json' },
    ],
    body: {
      query: '{{message}}',
      history: [],
      deepThinkingEnabled: false,
      deepThinkingLevel: null,
    },
    extract: [],
    success: { httpStatus: '200-299' },
    errorMessagePath: '$.content',
  },
  events: {
    typePath: '$.type',
    deltaType: 'delta',
    doneType: 'done',
    errorType: 'error',
    deltaPath: '$.content',
    errorPath: '$.content',
  },
};

const createDefaultStep = (): StepFormValue => ({
  key: `step_${Date.now()}`,
  name: '发送消息',
  method: 'POST',
  path: '/apps/{{externalApplicationId}}/chat',
  headers: [
    { key: 'Authorization', value: 'Bearer {{apiKey}}' },
    { key: 'Accept', value: 'application/json' },
    { key: 'Content-Type', value: 'application/json' },
  ],
  bodyText: JSON.stringify({ query: '{{message}}' }, null, 2),
  stream: false,
  hasStreamField: false,
  extract: [],
  success: { httpStatus: '200-299', bodyPath: '$.code', equals: 1 },
  errorMessagePath: '$.message',
});

const createSchemeAValues = (): IntegrationFormValues => ({
  schemeType: 'scheme_a',
  name: '方案A',
  remark: '',
  providerName: '',
  providerApiBaseUrl: '',
  providerApiKey: '',
  chatbotName: '',
  chatbotDescription: '',
  externalApplicationId: '',
  isActive: true,
  tenantIds: [],
  config: {
    steps: [
      {
        key: 'open_chat',
        name: '打开会话',
        method: 'GET',
        path: '/application/{{externalApplicationId}}/chat/open',
        headers: [
          { key: 'AUTHORIZATION', value: '{{apiKey}}' },
          { key: 'Accept', value: 'application/json' },
        ],
        bodyText: JSON.stringify({}, null, 2),
        stream: false,
        hasStreamField: false,
        extract: [{ name: 'chat_id', path: '$.data' }],
        success: { httpStatus: '200-299', bodyPath: '$.code', equals: 200 },
        errorMessagePath: '$.message',
      },
      {
        key: 'send_message',
        name: '发送消息',
        method: 'POST',
        path: '/application/chat_message/{{chat_id}}',
        headers: [
          { key: 'AUTHORIZATION', value: '{{apiKey}}' },
          { key: 'Accept', value: 'application/json' },
          { key: 'Content-Type', value: 'application/json' },
        ],
        bodyText: JSON.stringify({ message: '{{message}}', stream: false }, null, 2),
        stream: false,
        hasStreamField: true,
        extract: [{ name: 'chat_id', path: '$.data.chat_id' }],
        success: { httpStatus: '200-299', bodyPath: '$.code', equals: 200 },
        errorMessagePath: '$.message',
      },
    ],
    answerPaths: ['$.data.content', '$.data.answer_list.0.content'],
    streamingText: '',
  },
});

const createSchemeBValues = (): IntegrationFormValues => ({
  schemeType: 'scheme_b',
  name: '方案B',
  remark: '',
  providerName: 'FlowMesh',
  providerApiBaseUrl: 'https://flowmesh-api.kmyszkj.com/api/open/v1',
  providerApiKey: '',
  chatbotName: '',
  chatbotDescription: '',
  externalApplicationId: '',
  isActive: true,
  tenantIds: [],
  config: {
    steps: [
      {
        key: 'send_message',
        name: '发送消息',
        method: 'POST',
        path: '/apps/{{externalApplicationId}}/chat',
        headers: [
          { key: 'Authorization', value: 'Bearer {{apiKey}}' },
          { key: 'Accept', value: 'application/json' },
          { key: 'Content-Type', value: 'application/json' },
        ],
        bodyText: JSON.stringify({ query: '{{message}}' }, null, 2),
        stream: false,
        hasStreamField: false,
        extract: [{ name: 'sessionId', path: '$.data.sessionId' }],
        success: { httpStatus: '200-299', bodyPath: '$.code', equals: 1 },
        errorMessagePath: '$.message',
      },
    ],
    answerPaths: ['$.data.answer'],
    streamingText: JSON.stringify(FLOWMESH_STREAMING_CONFIG, null, 2),
  },
});

const SCHEME_TEMPLATES: SchemeTemplate[] = [
  {
    key: 'scheme_a',
    title: '方案A',
    subtitle: '多步骤 JSON API 流程',
    createValues: createSchemeAValues,
  },
  {
    key: 'scheme_b',
    title: '方案B',
    subtitle: 'FlowMesh LLM 流式对话',
    createValues: createSchemeBValues,
  },
];

const jsonText = (value: unknown) => JSON.stringify(value ?? {}, null, 2);

const parseJsonBody = (value: string | undefined, label: string) => {
  const text = String(value || '').trim() || '{}';
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed === null || typeof parsed !== 'object') {
      throw new Error(`${label} 必须是 JSON 对象或数组`);
    }
    return parsed as Record<string, unknown> | unknown[];
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(`${label} 不是有效 JSON`);
    }
    throw error;
  }
};

const parseEquals = (value: unknown) => {
  const text = String(value ?? '').trim();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as string | number | boolean | null;
  } catch {
    return text;
  }
};

const formStepFromConfig = (step: ThirdPartyChatbotApiStep): StepFormValue => {
  const body = step.body ?? {};
  const hasStreamField = !Array.isArray(body) && typeof body === 'object' && body !== null && 'stream' in body;
  const stream = hasStreamField ? Boolean((body as Record<string, unknown>).stream) : false;
  return {
    ...step,
    bodyText: jsonText(body),
    stream,
    hasStreamField,
    headers: step.headers || [],
    extract: step.extract || [],
    success: step.success || { httpStatus: '200-299' },
    errorMessagePath: step.errorMessagePath || '$.message',
  };
};

const formValuesFromRecord = (record: ThirdPartyChatbotIntegrationRecord): IntegrationFormValues => ({
  schemeType: record.schemeType,
  name: record.name,
  remark: record.remark,
  providerName: record.providerName,
  providerApiBaseUrl: record.providerApiBaseUrl,
  providerApiKey: '',
  chatbotName: record.chatbotName,
  chatbotDescription: record.chatbotDescription,
  externalApplicationId: record.externalApplicationId,
  isActive: record.isActive,
  tenantIds: record.authorizedTenantIds,
  config: {
    steps: (record.config.steps || []).map(formStepFromConfig),
    answerPaths: record.config.answerPaths || [],
    streamingText: record.config.streaming ? jsonText(record.config.streaming) : '',
  },
});

const normalizePayload = (values: IntegrationFormValues): ThirdPartyChatbotIntegrationPayload => {
  const streamingText = String(values.config.streamingText || '').trim();
  const parsedStreaming = streamingText ? parseJsonBody(streamingText, '流式配置') : undefined;
  if (Array.isArray(parsedStreaming)) {
    throw new Error('流式配置必须是 JSON 对象');
  }
  const streaming = parsedStreaming as ThirdPartyChatbotIntegrationConfig['streaming'];
  const steps = (values.config.steps || []).map((step, index) => {
    const body = parseJsonBody(step.bodyText, `步骤 ${index + 1} 请求体`);
    if (!Array.isArray(body) && typeof body === 'object' && body !== null && step.hasStreamField) {
      body.stream = Boolean(step.stream);
    }
    return {
      key: String(step.key || `step_${index + 1}`).trim(),
      name: String(step.name || `步骤 ${index + 1}`).trim(),
      method: step.method,
      path: String(step.path || '').trim(),
      headers: (step.headers || [])
        .map((header) => ({ key: String(header.key || '').trim(), value: String(header.value || '') }))
        .filter((header) => header.key),
      body,
      extract: (step.extract || [])
        .map((item) => ({ name: String(item.name || '').trim(), path: String(item.path || '').trim() }))
        .filter((item) => item.name && item.path),
      success: {
        httpStatus: String(step.success?.httpStatus || '200-299').trim(),
        bodyPath: String(step.success?.bodyPath || '').trim(),
        equals: parseEquals(step.success?.equals),
      },
      errorMessagePath: String(step.errorMessagePath || '').trim(),
    };
  });

  return {
    schemeType: values.schemeType || 'scheme_a',
    name: values.name.trim(),
    remark: values.remark || '',
    providerName: values.providerName.trim(),
    providerApiBaseUrl: values.providerApiBaseUrl.trim(),
    providerApiKey: values.providerApiKey?.trim() || undefined,
    chatbotName: values.chatbotName.trim(),
    chatbotDescription: values.chatbotDescription || '',
    externalApplicationId: values.externalApplicationId.trim(),
    config: {
      schemeType: values.schemeType || 'scheme_a',
      steps,
      answerPaths: (values.config.answerPaths || []).map((path) => path.trim()).filter(Boolean),
      ...(streaming ? { streaming } : {}),
    } satisfies ThirdPartyChatbotIntegrationConfig,
    isActive: values.isActive,
    tenantIds: values.tenantIds || [],
  };
};

export const ThirdPartyChatbotSettingsPage = () => {
  const [integrations, setIntegrations] = useState<ThirdPartyChatbotIntegrationRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [schemeModalOpen, setSchemeModalOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ThirdPartyChatbotIntegrationRecord | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ThirdPartyChatbotIntegrationTestResult | null>(null);
  const [form] = Form.useForm<IntegrationFormValues>();

  const activeTenants = useMemo(() => tenants.filter((tenant) => tenant.isActive), [tenants]);
  const activeTenantOptions = useMemo(
    () => activeTenants.map((tenant) => ({ label: tenant.name, value: tenant.id })),
    [activeTenants],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [integrationData, tenantData] = await Promise.all([
        fetchPlatformThirdPartyChatbotIntegrations(),
        fetchTenants({ page_size: 1000, include_hidden: true }),
      ]);
      setIntegrations(integrationData.results);
      setTenants(tenantData.results);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCreateSchemeSelect = () => {
    setEditingRecord(null);
    setTestResult(null);
    setSchemeModalOpen(true);
  };

  const openCreateSchemeEditor = (template: SchemeTemplate) => {
    form.resetFields();
    form.setFieldsValue(template.createValues());
    setSchemeModalOpen(false);
    setEditorOpen(true);
  };

  const openEdit = (record: ThirdPartyChatbotIntegrationRecord) => {
    setEditingRecord(record);
    setTestResult(null);
    form.resetFields();
    form.setFieldsValue(formValuesFromRecord(record));
    setEditorOpen(true);
  };

  const submitIntegration = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const payload = normalizePayload(values);
      if (editingRecord) {
        await updatePlatformThirdPartyChatbotIntegration(editingRecord.id, payload);
        message.success('方案已更新');
      } else {
        await createPlatformThirdPartyChatbotIntegration(payload);
        message.success('方案已创建');
      }
      setEditorOpen(false);
      await loadData();
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const removeIntegration = async (record: ThirdPartyChatbotIntegrationRecord) => {
    await deletePlatformThirdPartyChatbotIntegration(record.id);
    message.success('方案已删除');
    await loadData();
  };

  const runDraftTest = async () => {
    const values = await form.validateFields();
    const question = String(values.testQuestion || '').trim();
    if (!question) {
      message.warning('请输入测试问题');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const payload = normalizePayload(values);
      const result = await testPlatformThirdPartyChatbotIntegrationDraft({
        ...payload,
        integrationId: editingRecord?.id ?? null,
        question,
      });
      setTestResult(result);
    } catch (error) {
      const data = (error as { response?: { data?: Partial<ThirdPartyChatbotIntegrationTestResult> } }).response?.data;
      if (data) {
        setTestResult({
          success: Boolean(data.success),
          answer: data.answer || '',
          message: data.message || '测试失败',
          steps: data.steps || [],
        });
      }
    } finally {
      setTesting(false);
    }
  };

  const columns: ColumnsType<ThirdPartyChatbotIntegrationRecord> = [
    {
      title: '方案',
      dataIndex: 'name',
      render: (_, record) => (
        <Space size="middle">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
            <IconRobot size={20} />
          </span>
          <div>
            <div className="font-semibold text-slate-900">{record.name}</div>
            <div className="text-xs text-slate-500">{record.schemeTypeLabel}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '供应商',
      dataIndex: 'providerName',
      render: (_, record) => (
        <div>
          <div className="text-sm text-slate-800">{record.providerName}</div>
          <code className="text-xs text-slate-500">{record.providerApiBaseUrl}</code>
        </div>
      ),
    },
    {
      title: '机器人应用',
      dataIndex: 'chatbotName',
      render: (_, record) => (
        <div>
          <div className="text-sm text-slate-800">{record.chatbotName}</div>
          <code className="text-xs text-slate-500">{record.externalApplicationId}</code>
        </div>
      ),
    },
    {
      title: '公司授权',
      dataIndex: 'authorizedTenantIds',
      width: 120,
      render: (tenantIds: number[]) => <Tag color="processing">{tenantIds.length} 家</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 100,
      render: (isActive: boolean) => <Tag color={isActive ? 'success' : 'default'}>{isActive ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<IconEdit size={14} />} onClick={() => openEdit(record)} />
          <Popconfirm title="删除方案" description="删除后会同步移除对应机器人和公司授权。" onConfirm={() => void removeIntegration(record)}>
            <Button size="small" danger icon={<IconTrash size={14} />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const stepItems = (fields: Array<{ key: number; name: number }>, remove: (index: number | number[]) => void) => fields.map((field, index) => ({
    key: field.key,
    label: (
      <div className="flex items-center justify-between gap-3 pr-4">
        <span className="font-semibold text-slate-800">步骤 {index + 1}</span>
        <Space size="small">
          <Tag color="blue">API</Tag>
          <Button
            size="small"
            danger
            icon={<IconTrash size={14} />}
            onClick={(event) => {
              event.stopPropagation();
              remove(field.name);
            }}
          />
        </Space>
      </div>
    ),
    children: (
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Form.Item name={[field.name, 'key']} label="步骤标识" rules={[{ required: true, message: '请输入步骤标识' }]}>
            <Input />
          </Form.Item>
          <Form.Item name={[field.name, 'name']} label="步骤名称" rules={[{ required: true, message: '请输入步骤名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name={[field.name, 'method']} label="请求方式" rules={[{ required: true, message: '请选择请求方式' }]}>
            <Select options={METHOD_OPTIONS} />
          </Form.Item>
          <Form.Item name={[field.name, 'stream']} label="请求体 stream" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name={[field.name, 'hasStreamField']} hidden valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>
        <Form.Item name={[field.name, 'path']} label="请求路径" rules={[{ required: true, message: '请输入请求路径' }]}>
          <Input placeholder="/application/{{externalApplicationId}}/chat/open" />
        </Form.Item>

        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="mb-3 text-sm font-semibold text-slate-700">请求头</div>
          <Form.List name={[field.name, 'headers']}>
            {(headerFields, { add, remove: removeHeader }) => (
              <div className="space-y-2">
                {headerFields.map((headerField) => (
                  <div key={headerField.key} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
                    <Form.Item name={[headerField.name, 'key']} className="mb-0">
                      <Input placeholder="Header" />
                    </Form.Item>
                    <Form.Item name={[headerField.name, 'value']} className="mb-0">
                      <Input placeholder="Value" />
                    </Form.Item>
                    <Button icon={<IconTrash size={14} />} onClick={() => removeHeader(headerField.name)} />
                  </div>
                ))}
                <Button type="dashed" icon={<IconPlus size={14} />} onClick={() => add({ key: '', value: '' })}>
                  添加请求头
                </Button>
              </div>
            )}
          </Form.List>
        </div>

        <Form.Item
          name={[field.name, 'bodyText']}
          label="请求体 JSON"
          rules={[
            {
              validator: async (_, value) => {
                parseJsonBody(value, `步骤 ${index + 1} 请求体`);
              },
            },
          ]}
        >
          <Input.TextArea rows={7} className="font-mono" />
        </Form.Item>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <Form.Item name={[field.name, 'success', 'httpStatus']} label="成功 HTTP">
            <Input placeholder="200-299" />
          </Form.Item>
          <Form.Item name={[field.name, 'success', 'bodyPath']} label="成功字段">
            <Input placeholder="$.code" />
          </Form.Item>
          <Form.Item name={[field.name, 'success', 'equals']} label="期望值">
            <Input placeholder="200" />
          </Form.Item>
        </div>

        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="mb-3 text-sm font-semibold text-slate-700">变量提取</div>
          <Form.List name={[field.name, 'extract']}>
            {(extractFields, { add, remove: removeExtract }) => (
              <div className="space-y-2">
                {extractFields.map((extractField) => (
                  <div key={extractField.key} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
                    <Form.Item name={[extractField.name, 'name']} className="mb-0">
                      <Input placeholder="变量名" />
                    </Form.Item>
                    <Form.Item name={[extractField.name, 'path']} className="mb-0">
                      <Input placeholder="$.data" />
                    </Form.Item>
                    <Button icon={<IconTrash size={14} />} onClick={() => removeExtract(extractField.name)} />
                  </div>
                ))}
                <Button type="dashed" icon={<IconPlus size={14} />} onClick={() => add({ name: '', path: '' })}>
                  添加变量
                </Button>
              </div>
            )}
          </Form.List>
        </div>

        <Form.Item name={[field.name, 'errorMessagePath']} label="错误消息字段">
          <Input placeholder="$.message" />
        </Form.Item>
      </div>
    ),
  }));

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="page-hero">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold text-slate-900">
              <IconRobot size={24} className="text-brand-700" />
              <span>第三方会话机器人方案</span>
            </h1>
            <p className="mt-1 text-sm text-slate-500">平台级方案实例、接口流程与公司授权。</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:flex">
            <div className="rounded-xl border border-brand-100 bg-brand-50 px-4 py-2 text-center">
              <div className="text-xs font-semibold text-brand-700">方案实例</div>
              <div className="text-lg font-bold text-brand-700">{integrations.length} 个</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-center">
              <div className="text-xs font-semibold text-slate-500">授权公司</div>
              <div className="text-lg font-bold text-slate-700">
                {new Set(integrations.flatMap((item) => item.authorizedTenantIds)).size} 家
              </div>
            </div>
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm sm:p-6">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="page-section-title">方案列表</div>
            <Space wrap>
              <Button icon={<IconRefresh size={16} />} onClick={() => void loadData()}>
                刷新
              </Button>
              <Button type="primary" icon={<IconPlus size={16} />} onClick={openCreateSchemeSelect}>
                创建
              </Button>
            </Space>
          </div>
          <Table rowKey="id" columns={columns} dataSource={integrations} pagination={false} scroll={{ x: 920 }} />
        </div>
      </Spin>

      <Modal
        title="选择方案"
        open={schemeModalOpen}
        footer={null}
        onCancel={() => setSchemeModalOpen(false)}
        destroyOnHidden
      >
        <div className="space-y-3">
          {SCHEME_TEMPLATES.map((template) => (
            <button
              key={template.key}
              type="button"
              className="flex w-full items-start gap-3 rounded-xl border border-brand-100 bg-brand-50 p-4 text-left transition hover:border-brand-200 hover:bg-white"
              onClick={() => openCreateSchemeEditor(template)}
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white text-brand-700">
                <IconApi size={22} />
              </span>
              <span>
                <span className="block font-semibold text-slate-900">{template.title}</span>
                <span className="mt-1 block text-sm text-slate-500">{template.subtitle}</span>
              </span>
            </button>
          ))}
        </div>
      </Modal>

      <Modal
        title={editingRecord ? `编辑${editingRecord.schemeTypeLabel}` : `创建${form.getFieldValue('name') || '方案'}`}
        open={editorOpen}
        width="min(1180px, calc(100vw - 32px))"
        onCancel={() => setEditorOpen(false)}
        onOk={() => void submitIntegration()}
        okButtonProps={{ loading: saving }}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" className="max-h-[calc(100vh-220px)] overflow-y-auto pr-2 pt-2">
          <div className="rounded-xl border border-slate-100 bg-white p-4 sm:p-5">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Form.Item name="name" label="方案名称" rules={[{ required: true, message: '请输入方案名称' }]}>
                <Input maxLength={128} />
              </Form.Item>
              <Form.Item name="isActive" label="启用方案" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="tenantIds" label="公司授权">
                <Select mode="multiple" showSearch optionFilterProp="label" options={activeTenantOptions} />
              </Form.Item>
            </div>
            <Form.Item name="remark" label="备注">
              <Input.TextArea rows={3} maxLength={1000} showCount />
            </Form.Item>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">供应商</div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Form.Item name="providerName" label="供应商名称" rules={[{ required: true, message: '请输入供应商名称' }]}>
                  <Input maxLength={128} />
                </Form.Item>
                <Form.Item name="providerApiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
                  <Input placeholder="https://example.com/api" />
                </Form.Item>
                <Form.Item
                  name="providerApiKey"
                  label="应用密钥"
                  rules={editingRecord ? [] : [{ required: true, message: '请输入应用密钥' }]}
                >
                  <Input.Password placeholder={editingRecord ? '留空表示不修改' : undefined} />
                </Form.Item>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">机器人应用</div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Form.Item name="chatbotName" label="机器人名称" rules={[{ required: true, message: '请输入机器人名称' }]}>
                  <Input maxLength={128} />
                </Form.Item>
                <Form.Item
                  name="externalApplicationId"
                  label="第三方应用 ID"
                  rules={[{ required: true, message: '请输入第三方应用 ID' }]}
                >
                  <Input maxLength={128} />
                </Form.Item>
                <Form.Item name="chatbotDescription" label="机器人说明">
                  <Input maxLength={255} />
                </Form.Item>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">API 流程</div>
              <Form.List name={['config', 'steps']}>
                {(fields, { add, remove }) => (
                  <div className="space-y-3">
                    <Collapse items={stepItems(fields, remove)} />
                    <Button type="dashed" icon={<IconPlus size={14} />} onClick={() => add(createDefaultStep())}>
                      添加步骤
                    </Button>
                  </div>
                )}
              </Form.List>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">流式配置</div>
              <Form.Item
                name={['config', 'streamingText']}
                label="流式配置 JSON"
                rules={[
                  {
                    validator: async (_, value) => {
                      const text = String(value || '').trim();
                      if (text) parseJsonBody(text, '流式配置');
                    },
                  },
                ]}
              >
                <Input.TextArea rows={8} className="font-mono" placeholder="方案支持流式时填写，留空则运行时走同步接口" />
              </Form.Item>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">回复映射</div>
              <Form.List name={['config', 'answerPaths']}>
                {(fields, { add, remove }) => (
                  <div className="space-y-2">
                    {fields.map((field) => (
                      <div key={field.key} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                        <Form.Item name={field.name} className="mb-0" rules={[{ required: true, message: '请输入 JSON Path' }]}>
                          <Input placeholder="$.data.content" />
                        </Form.Item>
                        <Button icon={<IconTrash size={14} />} onClick={() => remove(field.name)} />
                      </div>
                    ))}
                    <Button type="dashed" icon={<IconPlus size={14} />} onClick={() => add('')}>
                      添加映射
                    </Button>
                  </div>
                )}
              </Form.List>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-3 text-base font-semibold text-slate-900">测试</div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Form.Item name="testQuestion" className="mb-0">
                  <Input placeholder="输入测试问题" />
                </Form.Item>
                <Button loading={testing} icon={<IconApi size={16} />} onClick={() => void runDraftTest()}>
                  测试
                </Button>
              </div>
              {testResult ? (
                <div className="mt-4 space-y-3">
                  <Alert type={testResult.success ? 'success' : 'error'} message={testResult.success ? '测试成功' : testResult.message || '测试失败'} />
                  {testResult.answer ? (
                    <pre className="max-h-48 overflow-auto rounded-xl bg-slate-50 p-3 text-sm text-slate-700">{testResult.answer}</pre>
                  ) : null}
                  <Table
                    size="small"
                    rowKey={(record) => `${record.key}-${record.name}`}
                    pagination={false}
                    dataSource={testResult.steps}
                    columns={[
                      { title: '步骤', dataIndex: 'name' },
                      { title: '状态码', dataIndex: 'statusCode', width: 100 },
                      {
                        title: '结果',
                        dataIndex: 'success',
                        width: 90,
                        render: (success: boolean) => <Tag color={success ? 'success' : 'error'}>{success ? '成功' : '失败'}</Tag>,
                      },
                      { title: '消息', dataIndex: 'message' },
                    ]}
                  />
                </div>
              ) : null}
            </div>
          </div>
        </Form>
      </Modal>
    </div>
  );
};
