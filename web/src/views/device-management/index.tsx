import {
  AppstoreOutlined,
  ClusterOutlined,
  DeleteOutlined,
  DesktopOutlined,
  EditOutlined,
  LinkOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { API_BASE_URL } from '../../api/client';
import {
  createDeviceApplication,
  createDeviceGroup,
  deleteDeviceGroup,
  fetchDeviceApplications,
  fetchDeviceGroups,
  fetchDeviceStats,
  fetchDevices,
  updateDevice,
  updateDeviceApplication,
  updateDeviceGroup,
  type DeviceApplicationPayload,
  type DeviceApplicationRecord,
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
import { useTenantScopeStore } from '../../store/tenant-scope';

type DeviceEditForm = {
  name: string;
  location?: string;
  applicationId?: number | null;
  groupId?: number | null;
};

type ApplicationForm = DeviceApplicationPayload;
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

const toSelectOptions = <T extends { id: number; name: string }>(items: T[]) =>
  items.map((item) => ({ label: item.name, value: item.id }));

const emptyGroupOption = [{ label: '未分组', value: null as number | null }];
const emptyApplicationOption = [{ label: '待绑定应用', value: null as number | null }];

const buildDeviceEventsWebSocketUrl = (token: string, tenantId: number | null) => {
  const baseUrl = API_BASE_URL.startsWith('http')
    ? new URL(API_BASE_URL)
    : new URL(API_BASE_URL, window.location.origin);
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  baseUrl.pathname = '/ws/devices/events/';
  baseUrl.search = '';
  baseUrl.searchParams.set('token', token);
  if (tenantId != null) {
    baseUrl.searchParams.set('tenantId', String(tenantId));
  }
  return baseUrl.toString();
};

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, trial: 0, permanent: 0 });
  const [groups, setGroups] = useState<DeviceGroupRecord[]>([]);
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [resourceOptions, setResourceOptions] = useState<ResourceOption[]>([]);
  const [scrollingTextOptions, setScrollingTextOptions] = useState<ResourceOption[]>([]);
  const [voiceToneOptions, setVoiceToneOptions] = useState<ResourceOption[]>([]);
  const [modelOptions, setModelOptions] = useState<ResourceOption[]>([]);
  const [commandGroupOptions, setCommandGroupOptions] = useState<ResourceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [filters, setFilters] = useState<DeviceListQuery>({
    status: 'all',
    enabledStatus: 'all',
    groupId: 'all',
    applicationId: 'all',
  });
  const [editingDevice, setEditingDevice] = useState<DeviceRecord | null>(null);
  const [editingApplication, setEditingApplication] = useState<DeviceApplicationRecord | null>(null);
  const [editingGroup, setEditingGroup] = useState<DeviceGroupRecord | null>(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | null>(null);
  const [realtimeConnected, setRealtimeConnected] = useState(false);
  const [applicationModalOpen, setApplicationModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [deviceForm] = Form.useForm<DeviceEditForm>();
  const [applicationForm] = Form.useForm<ApplicationForm>();
  const [groupForm] = Form.useForm<GroupForm>();
  const hasLoadedRef = useRef(false);
  const filtersRef = useRef(filters);
  const realtimeRefreshTimerRef = useRef<number | null>(null);
  const loadDataRef = useRef<((query?: DeviceListQuery) => Promise<void>) | null>(null);
  const { pathname } = useLocation();
  const token = useAuthStore((state) => state.token);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const tenant = useAuthStore((state) => state.tenant);
  const tenantScopeId = useTenantScopeStore((state) => state.tenantId);
  const isPlatformAdmin = hasPermission('tenant.management.view') || !tenant;
  const isTenantScopedRoute = pathname.startsWith('/tenants/');
  const canUseDeviceWorkspace = !isPlatformAdmin || isTenantScopedRoute;
  const realtimeTenantId = isTenantScopedRoute ? tenantScopeId : tenant?.id ?? null;
  const canCreateDevice = !isPlatformAdmin && hasPermission('devices.create');
  const canUpdateDevice = !isPlatformAdmin && hasPermission('devices.update');
  const canDeleteDevice = !isPlatformAdmin && hasPermission('devices.delete');

  const groupOptions = useMemo(() => toSelectOptions(groups), [groups]);
  const applicationOptions = useMemo(() => toSelectOptions(applications), [applications]);
  const selectedApplication = useMemo(
    () => applications.find((item) => item.id === selectedApplicationId) ?? applications[0] ?? null,
    [applications, selectedApplicationId],
  );
  const unboundDeviceCount = useMemo(() => devices.filter((item) => !item.applicationId).length, [devices]);

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
      const [deviceResponse, statsResponse, groupResponse, applicationResponse] = await Promise.all([
        fetchDevices({ ...query, keyword }),
        fetchDeviceStats(),
        fetchDeviceGroups(),
        fetchDeviceApplications(),
      ]);
      setDevices(deviceResponse.results);
      setStats(statsResponse);
      setGroups(groupResponse.results);
      setApplications(applicationResponse.results);
      setSelectedApplicationId((current) => current ?? applicationResponse.results[0]?.id ?? null);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setLoading(false);
    }
  };

  loadDataRef.current = loadData;

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

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

  useEffect(() => {
    if (!canUseDeviceWorkspace || !token || (isTenantScopedRoute && realtimeTenantId == null)) {
      setRealtimeConnected(false);
      return undefined;
    }

    let closed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const scheduleReload = () => {
      if (realtimeRefreshTimerRef.current != null) {
        window.clearTimeout(realtimeRefreshTimerRef.current);
      }
      realtimeRefreshTimerRef.current = window.setTimeout(() => {
        realtimeRefreshTimerRef.current = null;
        void loadDataRef.current?.(filtersRef.current);
      }, 250);
    };

    const connect = () => {
      socket = new WebSocket(buildDeviceEventsWebSocketUrl(token, realtimeTenantId));
      socket.onopen = () => {
        setRealtimeConnected(true);
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string };
          if (payload.type?.startsWith('device.')) {
            scheduleReload();
          }
        } catch {
          // Ignore malformed realtime payloads; the next valid event will refresh the table.
        }
      };
      socket.onclose = () => {
        if (closed) {
          return;
        }
        setRealtimeConnected(false);
        reconnectTimer = window.setTimeout(connect, 3000);
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closed = true;
      setRealtimeConnected(false);
      if (reconnectTimer != null) {
        window.clearTimeout(reconnectTimer);
      }
      if (realtimeRefreshTimerRef.current != null) {
        window.clearTimeout(realtimeRefreshTimerRef.current);
        realtimeRefreshTimerRef.current = null;
      }
      socket?.close();
    };
  }, [canUseDeviceWorkspace, isTenantScopedRoute, realtimeTenantId, token]);

  const handleSearch = () => {
    void loadData(filters);
  };

  const openDeviceEdit = (record: DeviceRecord) => {
    setEditingDevice(record);
    deviceForm.setFieldsValue({
      name: record.name,
      location: record.location,
      applicationId: record.applicationId ?? null,
      groupId: record.groupId ?? null,
    });
  };

  const handleDeviceSave = async () => {
    if (!editingDevice) return;
    const values = await deviceForm.validateFields();
    const nextDevice = await updateDevice(editingDevice.deviceCode, values);
    setDevices((current) => current.map((item) => (item.deviceCode === nextDevice.deviceCode ? nextDevice : item)));
    setEditingDevice(null);
    message.success('设备绑定已更新');
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

  const openApplicationConfig = (record: DeviceApplicationRecord) => {
    setSelectedApplicationId(record.id);
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
      setSelectedApplicationId(next.id);
      message.success('应用配置已更新');
    } else {
      const created = await createDeviceApplication(values);
      setApplications((current) => [created, ...current]);
      setSelectedApplicationId(created.id);
      message.success('应用已创建');
    }
    setApplicationModalOpen(false);
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

  const handleGroupDelete = async (record: DeviceGroupRecord) => {
    await deleteDeviceGroup(record.id);
    message.success('分组已删除');
    void loadData(filters);
  };

  const deviceColumns: ColumnsType<DeviceRecord> = [
    {
      title: '设备名称',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: '10%',
    },
    {
      title: '设备码',
      dataIndex: 'deviceCode',
      key: 'deviceCode',
      width: '12%',
      render: (value: string) => (
        <Typography.Text className="!text-xs" copyable>
          {value}
        </Typography.Text>
      ),
    },
    {
      title: '运行',
      dataIndex: 'status',
      key: 'status',
      width: '7%',
      render: (value: DeviceRecord['status']) => <Tag color={statusMap[value].color}>{statusMap[value].text}</Tag>,
    },
    {
      title: '授权状态',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      width: '8%',
      render: (value: boolean) => <Tag color={value ? 'success' : 'error'}>{value ? '正常' : '停用'}</Tag>,
    },
    {
      title: '绑定应用',
      dataIndex: 'applicationName',
      key: 'applicationName',
      width: '10%',
      render: (value: string) => (value ? <Tag color="cyan">{value}</Tag> : <Tag color="warning">待绑定</Tag>),
    },
    {
      title: '分组',
      dataIndex: 'groupName',
      key: 'groupName',
      width: '8%',
      render: (value: string) => value || '-',
    },
    {
      title: '授权',
      dataIndex: 'authorizationType',
      key: 'authorizationType',
      width: '8%',
      render: (value: DeviceAuthorizationType) => (
        <Tag color={authorizationMap[value].color}>{authorizationMap[value].text}</Tag>
      ),
    },
    {
      title: '到期时间',
      dataIndex: 'expiresAt',
      key: 'expiresAt',
      width: '10%',
      render: (value: string | null, record) => (record.authorizationType === 'permanent' ? '永久' : value || '-'),
    },
    { title: '软件版本', dataIndex: 'softwareVersion', key: 'softwareVersion', width: '8%', render: (value) => value || '-' },
    { title: '系统版本', dataIndex: 'systemVersion', key: 'systemVersion', width: '9%', render: (value) => value || '-' },
    { title: '主板信息', dataIndex: 'mainboardInfo', key: 'mainboardInfo', width: '10%', render: (value) => value || '-' },
    { title: '最近心跳', dataIndex: 'lastHeartbeat', key: 'lastHeartbeat', width: '10%', render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: '8%',
      render: (_, record) =>
        canUpdateDevice ? (
          <Tooltip title="绑定应用与分组">
            <Button size="small" icon={<LinkOutlined />} onClick={() => openDeviceEdit(record)}>
              绑定
            </Button>
          </Tooltip>
        ) : null,
    },
  ];

  const groupColumns: ColumnsType<DeviceGroupRecord> = [
    { title: '分组名称', dataIndex: 'name', key: 'name' },
    { title: '备注', dataIndex: 'remark', key: 'remark', render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      width: '18%',
      render: (_, record) => (
        <Space size={6}>
          {canUpdateDevice ? (
            <Button size="small" icon={<EditOutlined />} onClick={() => openGroupEdit(record)}>
              编辑
            </Button>
          ) : null}
          {canDeleteDevice ? (
            <Popconfirm
              title="删除分组"
              description={`确认删除「${record.name}」？设备会变为未分组。`}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void handleGroupDelete(record)}
            >
              <Button size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
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
            平台管理员需要先进入某个公司视图，再维护该公司的设备、应用和资源绑定。
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
              Device Code Runtime
            </div>
            <Typography.Title level={4} className="!mb-1 !font-semibold !text-slate-900">
              设备与应用
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              安卓端只上报设备码；后台负责设备归属、应用绑定和资源包配置。
            </Typography.Text>
          </div>
          <Space size={8}>
            <Tag color={realtimeConnected ? 'success' : 'default'}>
              {realtimeConnected ? '实时同步中' : '实时未连接'}
            </Tag>
            <Button icon={<ReloadOutlined />} onClick={() => loadData()}>
              刷新
            </Button>
          </Space>
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
            <Typography.Text type="secondary">待绑定</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-amber-600">{unboundDeviceCount}</div>
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Typography.Text type="secondary">应用数</Typography.Text>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-indigo-600">{applications.length}</div>
          </Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: 'devices',
            label: (
              <Space size={6}>
                <DesktopOutlined />
                设备
              </Space>
            ),
            children: (
              <Space direction="vertical" size={12} className="w-full">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(220px,1fr)_140px_140px_160px_160px_auto]">
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
                    value={filters.enabledStatus}
                    onChange={(value) => setFilters((current) => ({ ...current, enabledStatus: value }))}
                    options={[
                      { label: '全部授权', value: 'all' },
                      { label: '正常', value: 'enabled' },
                      { label: '停用', value: 'disabled' },
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
                  tableLayout="fixed"
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
              <Space direction="vertical" size={14} className="w-full">
                <div className="flex justify-end">
                  {canCreateDevice ? (
                    <Button type="primary" icon={<PlusOutlined />} onClick={openApplicationCreate}>
                      新建应用
                    </Button>
                  ) : null}
                </div>
                {applications.length === 0 ? (
                  <Empty description="暂无应用" />
                ) : (
                  <Row gutter={[12, 12]}>
                    {applications.map((item) => (
                      <Col xs={24} md={12} xl={8} key={item.id}>
                        <Card
                          variant="borderless"
                          className={`!h-full !rounded-xl !border !shadow-card ${
                            selectedApplication?.id === item.id ? '!border-teal-300' : '!border-slate-200/70'
                          }`}
                          onClick={() => setSelectedApplicationId(item.id)}
                        >
                          <Space direction="vertical" size={10} className="w-full">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <Typography.Title level={5} className="!mb-1 !truncate">
                                  {item.name}
                                </Typography.Title>
                                <Typography.Text className="!text-xs !text-slate-500" copyable>
                                  {item.code}
                                </Typography.Text>
                              </div>
                              <Tag color={item.isActive ? 'success' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
                            </div>
                            <Typography.Paragraph className="!mb-0 !min-h-[40px] !text-[13px] !text-slate-500">
                              {item.description || '未填写说明'}
                            </Typography.Paragraph>
                            <Space size={[4, 4]} wrap>
                              <Tag>媒体 {item.resourceIds.length}</Tag>
                              <Tag>滚动文本 {item.scrollingTextIds.length}</Tag>
                              <Tag>音色 {item.voiceToneIds.length}</Tag>
                              <Tag>模型 {item.modelAssetIds.length}</Tag>
                              <Tag>指令 {item.commandGroupIds.length}</Tag>
                            </Space>
                            {canUpdateDevice ? (
                              <Button icon={<SettingOutlined />} onClick={() => openApplicationConfig(item)}>
                                配置
                              </Button>
                            ) : null}
                          </Space>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                )}
                {selectedApplication ? (
                  <div className="rounded-xl border border-slate-200/70 bg-white p-4 shadow-card">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <Typography.Title level={5} className="!mb-1">
                          {selectedApplication.name}
                        </Typography.Title>
                        <Typography.Text type="secondary">当前应用资源包概览</Typography.Text>
                      </div>
                      {canUpdateDevice ? (
                        <Button icon={<SettingOutlined />} onClick={() => openApplicationConfig(selectedApplication)}>
                          打开配置
                        </Button>
                      ) : null}
                    </div>
                    <Divider className="!my-4" />
                    <Row gutter={[10, 10]}>
                      {[
                        ['媒体素材', selectedApplication.resourceIds.length, '图片 / 视频资源'],
                        ['滚动文本', selectedApplication.scrollingTextIds.length, '多语言滚动字幕'],
                        ['音色', selectedApplication.voiceToneIds.length, 'TTS 音色与展示资产'],
                        ['模型', selectedApplication.modelAssetIds.length, '数字人模型资产'],
                        ['指令组', selectedApplication.commandGroupIds.length, '控制与任务指令'],
                      ].map(([label, count, desc]) => (
                        <Col xs={12} md={8} xl={4} key={label}>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                            <Typography.Text type="secondary">{label}</Typography.Text>
                            <div className="mt-1 text-2xl font-semibold tabular-nums">{count}</div>
                            <div className="mt-1 text-xs text-slate-500">{desc}</div>
                          </div>
                        </Col>
                      ))}
                    </Row>
                  </div>
                ) : null}
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

      <Modal
        title="绑定设备"
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
          <Form.Item label="部署位置" name="location">
            <Input />
          </Form.Item>
          <Form.Item label="绑定应用" name="applicationId">
            <Select options={[...emptyApplicationOption, ...applicationOptions]} />
          </Form.Item>
          <Form.Item label="分组" name="groupId">
            <Select options={[...emptyGroupOption, ...groupOptions]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingApplication ? '应用配置' : '新建应用'}
        open={applicationModalOpen}
        onCancel={() => setApplicationModalOpen(false)}
        onOk={handleApplicationSave}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
        width="58vw"
      >
        <Form<ApplicationForm> form={applicationForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="应用名称" name="name" rules={[{ required: true, message: '请输入应用名称' }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="应用码" name="code" rules={[{ required: true, message: '请输入应用码' }]}>
                <Input disabled={!!editingApplication} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="说明" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item label="启用应用" name="isActive" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Divider className="!my-4" />
          <Form.Item label="图片 / 视频素材" name="resourceIds">
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
          <Form.Item label="指令组" name="commandGroupIds">
            <Select mode="multiple" options={commandGroupOptions} optionFilterProp="label" />
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
        width="42vw"
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
