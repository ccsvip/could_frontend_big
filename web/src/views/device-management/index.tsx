import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  PlusOutlined,
  WarningOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Form, Input, Modal, Row, Select, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchDevices, fetchDeviceStats, createDevice, type DeviceRecord } from '../../api/modules/devices';
import { useAuthStore } from '../../store/auth';

const statusMap: Record<DeviceRecord['status'], { color: string; text: string }> = {
  online: { color: 'success', text: '在线' },
  offline: { color: 'default', text: '离线' },
  maintaining: { color: 'processing', text: '维护中' },
};

type CreateDeviceForm = {
  id: string;
  name: string;
  location: string;
  status: DeviceRecord['status'];
};

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, maintaining: 0 });
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [form] = Form.useForm<CreateDeviceForm>();
  const hasLoadedRef = useRef(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreateDevice = hasPermission('devices.create');

  const loadData = async () => {
    setLoading(true);
    try {
      const [deviceResponse, statsResponse] = await Promise.all([fetchDevices(), fetchDeviceStats()]);
      setDevices(deviceResponse.results);
      setStats(statsResponse);
    } catch {
      // 错误已在拦截器中处理，无需重复显示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;
    void loadData();
  }, []);

  const handleCreateDevice = async () => {
    try {
      const values = await form.validateFields();
      const newDevice = await createDevice(values);

      setDevices((current) => [newDevice, ...current]);
      setStats((current) => ({
        ...current,
        total: current.total + 1,
        [values.status]: current[values.status] + 1,
      }));

      message.success('设备创建成功');
      setCreateVisible(false);
      form.resetFields();
    } catch {
      // 错误已在拦截器中处理，无需重复显示
    }
  };

  const columns: ColumnsType<DeviceRecord> = useMemo(
    () => [
      {
        title: '设备编号',
        dataIndex: 'id',
        key: 'id',
        width: 140,
      },
      {
        title: '设备名称',
        dataIndex: 'name',
        key: 'name',
      },
      {
        title: '部署位置',
        dataIndex: 'location',
        key: 'location',
        width: 220,
      },
      {
        title: '运行状态',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        render: (status: DeviceRecord['status']) => <Tag color={statusMap[status].color}>{statusMap[status].text}</Tag>,
      },
      {
        title: '最近心跳',
        dataIndex: 'lastHeartbeat',
        key: 'lastHeartbeat',
        width: 190,
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" size={16} className="w-full">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-700">
              <span className="inline-block h-1 w-1 rounded-full bg-teal-600" />
              AI Device Orchestration
            </div>
            <Typography.Title level={4} className="!mb-1 !text-slate-900 !font-semibold">
              数字人终端运行总览
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              实时监控设备状态、连接质量与在线活跃度，保障 AI 服务稳定交付
            </Typography.Text>
          </div>
          {canCreateDevice ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              size="large"
              onClick={() => setCreateVisible(true)}
            >
              新建设备
            </Button>
          ) : null}
        </div>
      </div>

      <Row gutter={[14, 14]}>
        <Col xs={24} md={8}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <Typography.Text type="secondary" className="!text-[13px]">在线设备</Typography.Text>
                <div className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{stats.online}</div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                <CheckCircleOutlined className="text-lg" />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <Typography.Text type="secondary" className="!text-[13px]">维护中</Typography.Text>
                <div className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{stats.maintaining}</div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <ClockCircleOutlined className="text-lg" />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <Typography.Text type="secondary" className="!text-[13px]">离线设备</Typography.Text>
                <div className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{stats.offline}</div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                <WarningOutlined className="text-lg" />
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        variant="borderless"
        className="!rounded-xl !border !border-slate-200/70 !shadow-card"
        title={
          <Space size={8}>
            <CloudServerOutlined className="text-teal-700" />
            <span>设备资产列表</span>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={devices}
          rowKey="id"
          loading={loading}
          scroll={{ x: 760 }}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          locale={{ emptyText: '暂无设备数据，请先新增设备' }}
        />
      </Card>

      <Modal
        title="新建设备"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        onOk={handleCreateDevice}
        okText="确认新增"
        cancelText="取消"
        destroyOnHidden
        forceRender
      >
        <Form<CreateDeviceForm> form={form} layout="vertical" initialValues={{ status: 'offline' }}>
          <Form.Item label="设备编号" name="id" rules={[{ required: true, message: '请输入设备编号' }]}>
            <Input placeholder="例如：DV-10004" />
          </Form.Item>
          <Form.Item label="设备名称" name="name" rules={[{ required: true, message: '请输入设备名称' }]}>
            <Input placeholder="请输入设备名称" />
          </Form.Item>
          <Form.Item label="部署位置" name="location" rules={[{ required: true, message: '请输入部署位置' }]}>
            <Input placeholder="请输入部署位置" />
          </Form.Item>
          <Form.Item label="运行状态" name="status" rules={[{ required: true, message: '请选择运行状态' }]}>
            <Select
              options={[
                { value: 'online', label: '在线' },
                { value: 'offline', label: '离线' },
                { value: 'maintaining', label: '维护中' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
