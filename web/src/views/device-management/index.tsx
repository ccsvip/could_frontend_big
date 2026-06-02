import {
  AppstoreOutlined,
  CheckCircleOutlined,
  ClusterOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  createDeviceApplication,
  createDeviceAuthorizationCode,
  createDeviceGroup,
  fetchDeviceApplications,
  fetchDeviceAuthorizationCodes,
  fetchDeviceGroups,
  fetchDeviceStats,
  fetchDevices,
  updateDevice,
  updateDeviceApplication,
  updateDeviceGroup,
  type DeviceApplicationPayload,
  type DeviceApplicationRecord,
  type DeviceAuthorizationCodePayload,
  type DeviceAuthorizationCodeRecord,
  type DeviceAuthorizationType,
  type DeviceGroupPayload,
  type DeviceGroupRecord,
  type DeviceListQuery,
  type DeviceRecord,
} from '../../api/modules/devices';
import { fetchCommandGroups } from '../../api/modules/commands';
import { fetchImageResources, fetchVideoResources } from '../../api/modules/resources';
import { fetchScrollingTexts } from '../../api/modules/scrolling-texts';
import { fetchModelAssets } from '../../api/modules/models';
import { fetchVoiceTones } from '../../api/modules/voice-tones';
import { useAuthStore } from '../../store/auth';

type DeviceEditForm = {
  name: string;
  groupId?: number | null;
};

type ApplicationForm = DeviceApplicationPayload;
type AuthorizationCodeForm = DeviceAuthorizationCodePayload;
type GroupForm = DeviceGroupPayload;

type ResourceOption = {
  label: string;
  value: number;
};

const statusMap: Record<DeviceRecord['status'], { color: string; text: string }> = {
  online: { color: 'success', text: '在线' },
  offline: { color: 'default', text: '离线' },
};

const authorizationMap: Record<DeviceAuthorizationType, { color: string; text: string }> = {
  permanent: { color: 'geekblue', text: '永久' },
  trial: { color: 'gold', text: '试用' },
};

const codeStatusMap: Record<DeviceAuthorizationCodeRecord['status'], { color: string; text: string }> = {
  unused: { color: 'success', text: '未使用' },
  used: { color: 'default', text: '已使用' },
  disabled: { color: 'error', text: '已禁用' },
};

const toSelectOptions = <T extends { id: number; name: string }>(items: T[]) =>
  items.map((item) => ({ label: item.name, value: item.id }));

const emptyOption = [{ label: '未分组', value: null as number | null }];

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, trial: 0, permanent: 0 });
  const [groups, setGroups] = useState<DeviceGroupRecord[]>([]);
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [authorizationCodes, setAuthorizationCodes] = useState<DeviceAuthorizationCodeRecord[]>([]);
  const [resourceOptions, setResourceOptions] = useState<ResourceOption[]>([]);
  const [scrollingTextOptions, setScrollingTextOptions] = useState<ResourceOption[]>([]);
  const [voiceToneOptions, setVoiceToneOptions] = useState<ResourceOption[]>([]);
  const [modelOptions, setModelOptions] = useState<ResourceOption[]>([]);
  const [commandGroupOptions, setCommandGroupOptions] = useState<ResourceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [filters, setFilters] = useState<DeviceListQuery>({ status: 'all', groupId: 'all', applicationId: 'all' });
  const [editingDevice, setEditingDevice] = useState<DeviceRecord | null>(null);
  const [editingApplication, setEditingApplication] = useState<DeviceApplicationRecord | null>(null);
  const [editingGroup, setEditingGroup] = useState<DeviceGroupRecord | null>(null);
  const [applicationModalOpen, setApplicationModalOpen] = useState(false);
  const [authorizationModalOpen, setAuthorizationModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [deviceForm] = Form.useForm<DeviceEditForm>();
  const [applicationForm] = Form.useForm<ApplicationForm>();
  const [authorizationForm] = Form.useForm<AuthorizationCodeForm>();
  const [groupForm] = Form.useForm<GroupForm>();
  const hasLoadedRef = useRef(false);
  const { pathname } = useLocation();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const tenant = useAuthStore((state) => state.tenant);
  const isPlatformAdmin = hasPermission('tenant.management.view') || !tenant;
  const isTenantScopedRoute = pathname.startsWith('/tenants/');
  const canUseDeviceWorkspace = !isPlatformAdmin || isTenantScopedRoute;
  const canCreateDevice = !isPlatformAdmin && hasPermission('devices.create');
  const canUpdateDevice = !isPlatformAdmin && hasPermission('devices.update');

  const groupOptions = useMemo(() => toSelectOptions(groups), [groups]);
  const applicationOptions = useMemo(() => toSelectOptions(applications), [applications]);

  const loadResourceOptions = async () => {
    try {
      const [images, videos, scrollingTexts, voiceTones, models, commandGroups] = await Promise.all([
        fetchImageResources({ pageSize: 100 }),
        fetchVideoResources({ pageSize: 100 }),
        fetchScrollingTexts({ pageSize: 100, status: 'active' }),
        fetchVoiceTones({ pageSize: 100 }),
        fetchModelAssets({ pageSize: 100 }),
        fetchCommandGroups({ pageSize: 100 }),
      ]);
      setResourceOptions([
        ...images.results.map((item) => ({ label: `图片 · ${item.name}`, value: item.id })),
        ...videos.results.map((item) => ({ label: `视频 · ${item.name}`, value: item.id })),
      ]);
      setScrollingTextOptions(scrollingTexts.results.map((item) => ({ label: item.title, value: item.id })));
      setVoiceToneOptions(toSelectOptions(voiceTones.results));
      setModelOptions(toSelectOptions(models.results));
      setCommandGroupOptions(toSelectOptions(commandGroups.results));
    } catch {
      setResourceOptions([]);
      setScrollingTextOptions([]);
      setVoiceToneOptions([]);
      setModelOptions([]);
      setCommandGroupOptions([]);
    }
  };

  const loadData = async (query: DeviceListQuery = filters) => {
    setLoading(true);
    try {
      const [deviceResponse, statsResponse, groupResponse, applicationResponse, codeResponse] = await Promise.all([
        fetchDevices({ ...query, keyword }),
        fetchDeviceStats(),
        fetchDeviceGroups(),
        fetchDeviceApplications(),
        fetchDeviceAuthorizationCodes(),
      ]);
      setDevices(deviceResponse.results);
      setStats(statsResponse);
      setGroups(groupResponse.results);
      setApplications(applicationResponse.results);
      setAuthorizationCodes(codeResponse.results);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canUseDeviceWorkspace) {
      return;
    }
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;
    void loadData();
    void loadResourceOptions();
  }, [canUseDeviceWorkspace]);

  const handleSearch = () => {
    void loadData(filters);
  };

  const openDeviceEdit = (record: DeviceRecord) => {
    setEditingDevice(record);
    deviceForm.setFieldsValue({ name: record.name, groupId: record.groupId ?? null });
  };

  const handleDeviceSave = async () => {
    if (!editingDevice) return;
    const values = await deviceForm.validateFields();
    const nextDevice = await updateDevice(editingDevice.deviceCode, values);
    setDevices((current) => current.map((item) => (item.deviceCode === nextDevice.deviceCode ? nextDevice : item)));
    setEditingDevice(null);
    message.success('设备信息已更新');
  };

  const openApplicationCreate = () => {
    setEditingApplication(null);
    applicationForm.resetFields();
    applicationForm.setFieldsValue({
      isActive: true,
      resourceIds: [],
      scrollingTextIds: [],
      voiceToneIds: [],
      modelAssetIds: [],
      commandGroupIds: [],
    });
    setApplicationModalOpen(true);
  };

  const openApplicationEdit = (record: DeviceApplicationRecord) => {
    setEditingApplication(record);
    applicationForm.setFieldsValue({
      name: record.name,
      code: record.code,
      description: record.description,
      isActive: record.isActive,
      resourceIds: record.resourceIds,
      scrollingTextIds: record.scrollingTextIds,
      voiceToneIds: record.voiceToneIds,
      modelAssetIds: record.modelAssetIds,
      commandGroupIds: record.commandGroupIds,
    });
    setApplicationModalOpen(true);
  };

  const handleApplicationSave = async () => {
    const values = await applicationForm.validateFields();
    if (editingApplication) {
      const next = await updateDeviceApplication(editingApplication.id, values);
      setApplications((current) => current.map((item) => (item.id === next.id ? next : item)));
      message.success('应用已更新');
    } else {
      const created = await createDeviceApplication(values);
      setApplications((current) => [created, ...current]);
      message.success('应用已创建');
    }
    setApplicationModalOpen(false);
  };

  const openAuthorizationCreate = () => {
    authorizationForm.resetFields();
    authorizationForm.setFieldsValue({ authorizationType: 'trial' });
    setAuthorizationModalOpen(true);
  };

  const handleAuthorizationCreate = async () => {
    const values = await authorizationForm.validateFields();
    const created = await createDeviceAuthorizationCode({
      ...values,
      code: values.code.trim(),
      expiresAt: values.authorizationType === 'trial' ? values.expiresAt : null,
      remark: values.remark?.trim(),
    });
    setAuthorizationCodes((current) => [created, ...current]);
    setAuthorizationModalOpen(false);
    message.success(`授权已创建：${created.code}`);
  };

  const openGroupCreate = () => {
    setEditingGroup(null);
    groupForm.resetFields();
    setGroupModalOpen(true);
  };

  const openGroupEdit = (record: DeviceGroupRecord) => {
    setEditingGroup(record);
    groupForm.setFieldsValue({ name: record.name, remark: record.remark });
    setGroupModalOpen(true);
  };

  const handleGroupSave = async () => {
    const values = await groupForm.validateFields();
    if (editingGroup) {
      const next = await updateDeviceGroup(editingGroup.id, values);
      setGroups((current) => current.map((item) => (item.id === next.id ? next : item)));
      message.success('分组已更新');
    } else {
      const created = await createDeviceGroup(values);
      setGroups((current) => [created, ...current]);
      message.success('分组已创建');
    }
    setGroupModalOpen(false);
  };

  const deviceColumns: ColumnsType<DeviceRecord> = [
    {
      title: '设备名称',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 180,
    },
    {
      title: '设备码',
      dataIndex: 'deviceCode',
      key: 'deviceCode',
      width: 190,
      render: (value: string) => <Typography.Text className="!text-xs" copyable>{value}</Typography.Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (value: DeviceRecord['status']) => <Tag color={statusMap[value].color}>{statusMap[value].text}</Tag>,
    },
    {
      title: '应用',
      dataIndex: 'applicationName',
      key: 'applicationName',
      width: 160,
      render: (value: string) => value || '-',
    },
    {
      title: '分组',
      dataIndex: 'groupName',
      key: 'groupName',
      width: 120,
      render: (value: string) => value || '-',
    },
    {
      title: '授权',
      dataIndex: 'authorizationType',
      key: 'authorizationType',
      width: 90,
      render: (value: DeviceAuthorizationType) => (
        <Tag color={authorizationMap[value].color}>{authorizationMap[value].text}</Tag>
      ),
    },
    {
      title: '到期时间',
      dataIndex: 'expiresAt',
      key: 'expiresAt',
      width: 170,
      render: (value: string | null, record) => (record.authorizationType === 'permanent' ? '永久' : value || '-'),
    },
    { title: '软件版本', dataIndex: 'softwareVersion', key: 'softwareVersion', width: 110, render: (value) => value || '-' },
    { title: '系统版本', dataIndex: 'systemVersion', key: 'systemVersion', width: 130, render: (value) => value || '-' },
    { title: '主板信息', dataIndex: 'mainboardInfo', key: 'mainboardInfo', width: 160, render: (value) => value || '-' },
    { title: '注册时间', dataIndex: 'registeredAt', key: 'registeredAt', width: 170, render: (value) => value || '-' },
    { title: '最后心跳', dataIndex: 'lastHeartbeat', key: 'lastHeartbeat', width: 170, render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 90,
      render: (_, record) =>
        canUpdateDevice ? (
          <Button size="small" icon={<EditOutlined />} onClick={() => openDeviceEdit(record)}>
            编辑
          </Button>
        ) : null,
    },
  ];

  const applicationColumns: ColumnsType<DeviceApplicationRecord> = [
    { title: '应用名称', dataIndex: 'name', key: 'name' },
    { title: '应用标识', dataIndex: 'code', key: 'code' },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      width: 90,
      render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '资源包',
      key: 'resources',
      render: (_, record) => (
        <Space size={[4, 4]} wrap>
          <Tag>媒体 {record.resourceIds.length}</Tag>
          <Tag>滚动文本 {record.scrollingTextIds.length}</Tag>
          <Tag>音色 {record.voiceToneIds.length}</Tag>
          <Tag>模型 {record.modelAssetIds.length}</Tag>
          <Tag>指令 {record.commandGroupIds.length}</Tag>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) =>
        canUpdateDevice ? (
          <Button size="small" icon={<EditOutlined />} onClick={() => openApplicationEdit(record)}>
            编辑
          </Button>
        ) : null,
    },
  ];

  const codeColumns: ColumnsType<DeviceAuthorizationCodeRecord> = [
    {
      title: '授权码',
      dataIndex: 'code',
      key: 'code',
      width: 170,
      render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>,
    },
    { title: '应用', dataIndex: 'applicationName', key: 'applicationName' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (value: DeviceAuthorizationCodeRecord['status']) => (
        <Tag color={codeStatusMap[value].color}>{codeStatusMap[value].text}</Tag>
      ),
    },
    {
      title: '授权类型',
      dataIndex: 'authorizationType',
      key: 'authorizationType',
      width: 100,
      render: (value: DeviceAuthorizationType) => (
        <Tag color={authorizationMap[value].color}>{authorizationMap[value].text}</Tag>
      ),
    },
    { title: '到期时间', dataIndex: 'expiresAt', key: 'expiresAt', width: 170, render: (value) => value || '永久' },
    { title: '使用设备', dataIndex: 'usedDeviceCode', key: 'usedDeviceCode', width: 170, render: (value) => value || '-' },
    { title: '备注', dataIndex: 'remark', key: 'remark', render: (value) => value || '-' },
  ];

  const groupColumns: ColumnsType<DeviceGroupRecord> = [
    { title: '分组名称', dataIndex: 'name', key: 'name' },
    { title: '备注', dataIndex: 'remark', key: 'remark', render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) =>
        canUpdateDevice ? (
          <Button size="small" icon={<EditOutlined />} onClick={() => openGroupEdit(record)}>
            编辑
          </Button>
        ) : null,
    },
  ];

  if (!canUseDeviceWorkspace) {
    return (
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={8}>
          <Typography.Title level={4} className="!mb-0">
            请选择公司
          </Typography.Title>
          <Typography.Text type="secondary">
            平台管理员只负责创建和管理公司；设备、应用、授权码和资源绑定由公司账号维护。
          </Typography.Text>
        </Space>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size={16} className="w-full">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-700">
              <span className="inline-block h-1 w-1 rounded-full bg-teal-600" />
              Android Device Authorization
            </div>
            <Typography.Title level={4} className="!mb-1 !font-semibold !text-slate-900">
              设备授权
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              管理安卓设备激活、应用资源包、一次性授权码与在线状态
            </Typography.Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={() => loadData()}>
            刷新
          </Button>
        </div>
      </div>

      <Row gutter={[14, 14]}>
        <Col xs={12} lg={6}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Typography.Text type="secondary">设备总数</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums">{stats.total}</div>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Typography.Text type="secondary">在线</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-emerald-600">{stats.online}</div>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Typography.Text type="secondary">试用授权</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-amber-600">{stats.trial}</div>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Typography.Text type="secondary">永久授权</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-indigo-600">{stats.permanent}</div>
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Tabs
          items={[
            {
              key: 'devices',
              label: (
                <Space size={6}>
                  <CheckCircleOutlined />
                  已激活设备
                </Space>
              ),
              children: (
                <Space direction="vertical" size={12} className="w-full">
                  <div className="grid gap-2 md:grid-cols-[minmax(220px,1fr)_160px_160px_160px_auto]">
                    <Input
                      value={keyword}
                      prefix={<SearchOutlined />}
                      placeholder="按设备名称或设备码搜索"
                      onChange={(event) => setKeyword(event.target.value)}
                      onPressEnter={handleSearch}
                    />
                    <Select
                      value={filters.status}
                      onChange={(value) => setFilters((current) => ({ ...current, status: value }))}
                      options={[
                        { label: '全部状态', value: 'all' },
                        { label: '在线', value: 'online' },
                        { label: '离线', value: 'offline' },
                      ]}
                    />
                    <Select
                      value={filters.applicationId}
                      onChange={(value) => setFilters((current) => ({ ...current, applicationId: value }))}
                      options={[{ label: '全部应用', value: 'all' }, ...applicationOptions]}
                    />
                    <Select
                      value={filters.groupId}
                      onChange={(value) => setFilters((current) => ({ ...current, groupId: value }))}
                      options={[{ label: '全部分组', value: 'all' }, ...groupOptions]}
                    />
                    <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                      查询
                    </Button>
                  </div>
                  <Table
                    columns={deviceColumns}
                    dataSource={devices}
                    rowKey="deviceCode"
                    loading={loading}
                    scroll={{ x: 1680 }}
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                  />
                </Space>
              ),
            },
            {
              key: 'applications',
              label: (
                <Space size={6}>
                  <AppstoreOutlined />
                  应用
                </Space>
              ),
              children: (
                <Space direction="vertical" size={12} className="w-full">
                  {canCreateDevice ? (
                    <div className="flex justify-end">
                      <Button type="primary" icon={<PlusOutlined />} onClick={openApplicationCreate}>
                        新建应用
                      </Button>
                    </div>
                  ) : null}
                  <Table columns={applicationColumns} dataSource={applications} rowKey="id" pagination={false} />
                </Space>
              ),
            },
            {
              key: 'codes',
              label: (
                <Space size={6}>
                  <KeyOutlined />
                  授权码
                </Space>
              ),
              children: (
                <Space direction="vertical" size={12} className="w-full">
                  {canCreateDevice ? (
                    <div className="flex justify-end">
                      <Button type="primary" icon={<PlusOutlined />} onClick={openAuthorizationCreate}>
                        生成授权
                      </Button>
                    </div>
                  ) : null}
                  <Table columns={codeColumns} dataSource={authorizationCodes} rowKey="id" scroll={{ x: 900 }} />
                </Space>
              ),
            },
            {
              key: 'groups',
              label: (
                <Space size={6}>
                  <ClusterOutlined />
                  分组
                </Space>
              ),
              children: (
                <Space direction="vertical" size={12} className="w-full">
                  {canCreateDevice ? (
                    <div className="flex justify-end">
                      <Button type="primary" icon={<PlusOutlined />} onClick={openGroupCreate}>
                        新建分组
                      </Button>
                    </div>
                  ) : null}
                  <Table columns={groupColumns} dataSource={groups} rowKey="id" pagination={false} />
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="编辑设备"
        open={!!editingDevice}
        onCancel={() => setEditingDevice(null)}
        onOk={handleDeviceSave}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form<DeviceEditForm> form={deviceForm} layout="vertical">
          <Form.Item label="设备名称" name="name" rules={[{ required: true, message: '请输入设备名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="分组" name="groupId">
            <Select options={[...emptyOption, ...groupOptions]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingApplication ? '编辑应用' : '新建应用'}
        open={applicationModalOpen}
        onCancel={() => setApplicationModalOpen(false)}
        onOk={handleApplicationSave}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
        width={720}
      >
        <Form<ApplicationForm> form={applicationForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="应用名称" name="name" rules={[{ required: true, message: '请输入应用名称' }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="应用标识" name="code" rules={[{ required: true, message: '请输入应用标识' }]}>
                <Input disabled={!!editingApplication} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="说明" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item label="状态" name="isActive" rules={[{ required: true, message: '请选择状态' }]}>
            <Select
              options={[
                { label: '启用', value: true },
                { label: '停用', value: false },
              ]}
            />
          </Form.Item>
          <Form.Item label="图片/视频资源" name="resourceIds">
            <Select mode="multiple" options={resourceOptions} optionFilterProp="label" />
          </Form.Item>
          <Form.Item label="滚动文本" name="scrollingTextIds">
            <Select mode="multiple" options={scrollingTextOptions} optionFilterProp="label" />
          </Form.Item>
          <Form.Item label="音色" name="voiceToneIds">
            <Select mode="multiple" options={voiceToneOptions} optionFilterProp="label" />
          </Form.Item>
          <Form.Item label="模型" name="modelAssetIds">
            <Select mode="multiple" options={modelOptions} optionFilterProp="label" />
          </Form.Item>
          <Form.Item label="指令分组" name="commandGroupIds">
            <Select mode="multiple" options={commandGroupOptions} optionFilterProp="label" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="生成授权"
        open={authorizationModalOpen}
        onCancel={() => setAuthorizationModalOpen(false)}
        onOk={handleAuthorizationCreate}
        okText="生成授权"
        cancelText="取消"
        destroyOnHidden
      >
        <Form<AuthorizationCodeForm> form={authorizationForm} layout="vertical">
          <Form.Item
            label="授权码"
            name="code"
            rules={[
              { required: true, message: '请输入授权码' },
              { whitespace: true, message: '请输入授权码' },
            ]}
          >
            <Input placeholder="请输入授权码" />
          </Form.Item>
          <Form.Item label="绑定应用" name="applicationId" rules={[{ required: true, message: '请选择应用' }]}>
            <Select options={applicationOptions} />
          </Form.Item>
          <Form.Item label="授权类型" name="authorizationType" rules={[{ required: true, message: '请选择授权类型' }]}>
            <Select
              options={[
                { label: '试用', value: 'trial' },
                { label: '永久', value: 'permanent' },
              ]}
            />
          </Form.Item>
          <Form.Item dependencies={['authorizationType']} noStyle>
            {({ getFieldValue }) =>
              getFieldValue('authorizationType') === 'trial' ? (
                <Form.Item label="到期时间" name="expiresAt" rules={[{ required: true, message: '请选择到期时间' }]}>
                  <Input type="datetime-local" />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item label="备注" name="remark">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingGroup ? '编辑分组' : '新建分组'}
        open={groupModalOpen}
        onCancel={() => setGroupModalOpen(false)}
        onOk={handleGroupSave}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form<GroupForm> form={groupForm} layout="vertical">
          <Form.Item label="分组名称" name="name" rules={[{ required: true, message: '请输入分组名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="备注" name="remark">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
