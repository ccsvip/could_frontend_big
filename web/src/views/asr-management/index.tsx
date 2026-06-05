import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Empty, Space, Tag, Typography, message } from 'antd';
import { ApiOutlined, AudioOutlined, CheckCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { fetchAsrStatus, testAsr, type AsrStatusRecord, type AsrTestResult } from '../../api/modules/asr';

const getEndpointHost = (baseUrl: string) => {
  try {
    return new URL(baseUrl).host || '-';
  } catch {
    return baseUrl || '-';
  }
};

export const AsrManagementPage = () => {
  const [status, setStatus] = useState<AsrStatusRecord | null>(null);
  const [testResult, setTestResult] = useState<AsrTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await fetchAsrStatus());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const endpointHost = useMemo(() => getEndpointHost(status?.baseUrl || ''), [status?.baseUrl]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testAsr();
      setTestResult(result);
      if (result.success) {
        message.success(`ASR 连接成功 (${result.latencyMs}ms)`);
      } else {
        message.error(result.message);
      }
    } finally {
      setTesting(false);
    }
  };

  if (!loading && !status) {
    return (
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Empty description={<span className="text-[14px] font-medium text-slate-500">暂无 ASR 状态</span>} />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card size="small" loading={loading}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Space size={10} className="mb-2">
              <AudioOutlined className="text-lg text-teal-700" />
              <Typography.Title level={4} className="!mb-0 !text-slate-900">
                ASR 管理
              </Typography.Title>
              <Tag color={status?.isActive ? 'success' : 'default'}>
                {status?.isActive ? '已启用' : '已停用'}
              </Tag>
              <Tag color={status?.configured ? 'blue' : 'warning'}>
                {status?.configured ? '配置完整' : '配置缺失'}
              </Tag>
            </Space>
            <Typography.Text className="text-slate-500">
              当前账号可查看平台 ASR 服务状态并发起连接测试，配置由超级管理员维护。
            </Typography.Text>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void loadStatus()}>
              刷新
            </Button>
            <Button type="primary" icon={<ApiOutlined />} loading={testing} onClick={() => void handleTest()}>
              测试连接
            </Button>
          </Space>
        </div>
      </Card>

      <Card size="small" title="服务状态">
        <Descriptions column={{ xs: 1, sm: 2, lg: 4 }} size="small">
          <Descriptions.Item label="Endpoint">{endpointHost}</Descriptions.Item>
          <Descriptions.Item label="Model">{status?.model || '-'}</Descriptions.Item>
          <Descriptions.Item label="Workspace">{status?.workspaceId || '-'}</Descriptions.Item>
          <Descriptions.Item label="Updated">{status?.updated_at || '-'}</Descriptions.Item>
        </Descriptions>

        {testResult ? (
          <Alert
            className="mt-4"
            type={testResult.success ? 'success' : 'error'}
            showIcon
            icon={testResult.success ? <CheckCircleOutlined /> : undefined}
            message={testResult.success ? `连接成功 (${testResult.latencyMs}ms)` : '连接失败'}
            description={testResult.message}
          />
        ) : null}
      </Card>
    </div>
  );
};
