import { CloudOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { Button, Card, Form, Input, InputNumber, Space, Switch, Table, Tag, Typography, message } from 'antd';
import { useEffect, useState } from 'react';
import {
  fetchMinioSettings,
  fetchTenantVideoQuotas,
  updateMinioSettings,
  updateTenantVideoQuotas,
  type MinioSettingsPayload,
  type TenantVideoQuotaRecord,
} from '../../api/modules/settings';

const formatMB = (value: number | null | undefined) => {
  if (value == null) {
    return '不限制';
  }
  return `${value.toLocaleString()} MB`;
};

export const MinioSettingsPage = () => {
  const [form] = Form.useForm<MinioSettingsPayload>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [quotaRows, setQuotaRows] = useState<TenantVideoQuotaRecord[]>([]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settings, quotaData] = await Promise.all([fetchMinioSettings(), fetchTenantVideoQuotas()]);
      form.setFieldsValue({ ...settings, secretKey: '' });
      setQuotaRows(quotaData.results);
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleSave = async () => {
    const values = await form.validateFields();
    const payload = { ...values };
    if (!payload.secretKey) {
      delete payload.secretKey;
    }
    setSaving(true);
    try {
      const settings = await updateMinioSettings(payload);
      const quotaData = await updateTenantVideoQuotas({
        items: quotaRows.map((item) => ({
          tenantId: item.tenantId,
          quotaLimited: item.quotaLimited,
          quotaMB: item.quotaLimited ? item.quotaMB : null,
        })),
      });
      form.setFieldsValue({ ...settings, secretKey: '' });
      setQuotaRows(quotaData.results);
      message.success('MinIO 设置已保存');
    } catch {
      // handled by interceptor
    } finally {
      setSaving(false);
    }
  };

  const updateQuotaRow = (tenantId: number, patch: Partial<TenantVideoQuotaRecord>) => {
    setQuotaRows((rows) => rows.map((row) => (row.tenantId === tenantId ? { ...row, ...patch } : row)));
  };

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <CloudOutlined className="text-xl" />
            </div>
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">MinIO 设置</Typography.Title>
              <Typography.Text className="!text-slate-500">配置平台视频直传对象存储，业务数据按公司对象前缀隔离。</Typography.Text>
            </div>
          </div>
          <Space wrap>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadData()}>刷新</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>保存</Button>
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Form<MinioSettingsPayload> form={form} layout="vertical" className="max-w-3xl">
          <Form.Item label="Endpoint" name="endpoint" rules={[{ required: true, message: '请输入 Endpoint' }]}>
            <Input placeholder="localhost:9000" />
          </Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="Access Key" name="accessKey" rules={[{ required: true, message: '请输入 Access Key' }]}>
              <Input autoComplete="off" />
            </Form.Item>
            <Form.Item label="Secret Key" name="secretKey" tooltip="留空表示不修改已保存的 Secret Key">
              <Input.Password autoComplete="new-password" placeholder="留空则不修改" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="Bucket" name="bucketName" rules={[{ required: true, message: '请输入 Bucket' }]}>
              <Input placeholder="digital-human" />
            </Form.Item>
            <Form.Item label="Region" name="region">
              <Input placeholder="us-east-1" />
            </Form.Item>
          </div>
          <Form.Item label="Public Base URL" name="publicBaseUrl">
            <Input placeholder="可选，例如 https://cdn.example.com/digital-human" />
          </Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="视频大小上限（MB）" name="videoMaxSizeMB" rules={[{ required: true, message: '请输入大小上限' }]}>
              <InputNumber min={1} precision={0} className="!w-full" />
            </Form.Item>
            <div className="grid grid-cols-3 gap-4">
              <Form.Item label="HTTPS" name="secure" valuePropName="checked">
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
              <Form.Item label="直传" name="isActive" valuePropName="checked">
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
              <Form.Item label="显示云端URL" name="allowVideoCloudUrl" valuePropName="checked">
                <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
              </Form.Item>
            </div>
          </div>
        </Form>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="mb-4">
          <Typography.Title level={4} className="!mb-1 !text-slate-900">公司视频额度</Typography.Title>
          <Typography.Text className="!text-slate-500">
            超级管理员可为每家公司单独设置视频上传容量额度；关闭限制后该公司不受容量额度限制。
          </Typography.Text>
        </div>
        <Table<TenantVideoQuotaRecord>
          rowKey="tenantId"
          loading={loading}
          dataSource={quotaRows}
          pagination={false}
          columns={[
            {
              title: '公司',
              dataIndex: 'tenantName',
              render: (_, record) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>{record.tenantName}</Typography.Text>
                  <Typography.Text className="!text-xs !text-slate-400">{record.tenantCode}</Typography.Text>
                </Space>
              ),
            },
            {
              title: '已用',
              dataIndex: 'usedMB',
              width: 130,
              render: (value) => `${Number(value || 0).toLocaleString()} MB`,
            },
            {
              title: '剩余',
              dataIndex: 'remainingMB',
              width: 130,
              render: (_, record) => (record.quotaLimited ? formatMB(record.remainingMB) : <Tag color="green">不限制</Tag>),
            },
            {
              title: '限制',
              dataIndex: 'quotaLimited',
              width: 120,
              render: (_, record) => (
                <Switch
                  checked={record.quotaLimited}
                  checkedChildren="限制"
                  unCheckedChildren="不限"
                  onChange={(checked) => updateQuotaRow(record.tenantId, { quotaLimited: checked, quotaMB: checked ? record.quotaMB ?? 1024 : null })}
                />
              ),
            },
            {
              title: '额度（MB）',
              dataIndex: 'quotaMB',
              width: 180,
              render: (_, record) => (
                <InputNumber
                  min={1}
                  precision={0}
                  disabled={!record.quotaLimited}
                  value={record.quotaMB ?? undefined}
                  className="!w-full"
                  onChange={(value) => updateQuotaRow(record.tenantId, { quotaMB: value == null ? null : Number(value) })}
                />
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
};
