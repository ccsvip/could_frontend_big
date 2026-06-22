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
import {
  buildDeviceEventsUnsubscribeCommand,
  buildRealtimeWebSocketUrl,
  createRealtimeCommandId,
  encodeRealtimeCommand,
  parseRealtimeMessage,
} from '../../api/realtime';
import {
  createDeviceApplication,
  createDeviceGroup,
  deleteDevice,
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
import { fetchAgentApplications, type AgentApplicationRecord } from '../../api/modules/applications';
import { useAuthStore } from '../../store/auth';
import { useTenantScopeStore } from '../../store/tenant-scope';

type DeviceEditForm = {
  applicationId?: number | null;
};

type ApplicationForm = DeviceApplicationPayload;
type GroupForm = DeviceGroupPayload;

type ResourceOption = {
  label: string;
  value: number;
};

type DeviceRuntimeDiagnostic = {
  level: 'ready' | 'warning' | 'blocked' | 'offline';
  label: string;
  color: string;
  hint: string;
  detail: string;
};

const resolveDeviceRuntimeDiagnostic = (device: DeviceRecord): DeviceRuntimeDiagnostic => {
  if (!device.isEnabled) {
    return {
      level: 'blocked',
      label: '授权停用',
      color: 'error',
      hint: '在授权中心重新启用或重新授权该设备。',
      detail: '安卓端会被运行时接口拒绝，无法继续拉取配置或发起语音链路。',
    };
  }

  if (!device.agentApplicationId) {
    return {
      level: 'blocked',
      label: '缺智能体',
      color: 'error',
      hint: '进入资源应用配置，为设备绑定的应用选择可用智能体。',
      detail: '运行时配置、语音问答和 ASR/TTS 链路都依赖资源应用绑定的智能体。',
    };
  }

  if (device.status === 'offline') {
    return {
      level: 'offline',
      label: '离线待心跳',
      color: 'default',
      hint: '检查安卓端设备码、网络和心跳接口响应。',
      detail: '后台暂未收到最近心跳，可能是设备未启动、设备码不一致或网络不可达。',
    };
  }

  if (!device.applicationId) {
    return {
      level: 'warning',
      label: '无应用绑定',
      color: 'warning',
      hint: '按需绑定应用，否则设备可运行但缺少应用级指令配置。',
      detail: '配置接口仍会返回智能体信息，但应用绑定相关配置为空。',
    };
  }

  return {
    level: 'ready',
    label: '运行就绪',
    color: 'success',
    hint: '可继续做配置拉取、ASR/TTS 与语音问答联调。',
    detail: '授权、资源应用、应用智能体和在线心跳都已具备。',
  };
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

const buildGeneratedApplicationCode = () => `device-app-${Date.now().toString(36)}`;

const isDeviceRealtimePayload = (payload: unknown): payload is { type: string } =>
  !!payload && typeof payload === 'object' && typeof (payload as { type?: unknown }).type === 'string';

const emptyApplicationOption = [{ label: '待绑定资源应用', value: null as number | null }];
const emptyAgentApplicationOption = [{ label: '待绑定智能体', value: null as number | null }];

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [deviceTotal, setDeviceTotal] = useState(0);
  const [devicePage, setDevicePage] = useState(1);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, trial: 0, permanent: 0 });
  const [groups, setGroups] = useState<DeviceGroupRecord[]>([]);
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [agentApplications, setAgentApplications] = useState<AgentApplicationRecord[]>([]);
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
  const devicePageRef = useRef(devicePage);
  const realtimeRefreshTimerRef = useRef<number | null>(null);
  const loadDataRef = useRef<((query?: DeviceListQuery, page?: number) => Promise<void>) | null>(null);
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
  const agentApplicationOptions = useMemo(() => toSelectOptions(agentApplications), [agentApplications]);
  const selectedApplication = useMemo(
    () => applications.find((item) => item.id === selectedApplicationId) ?? applications[0] ?? null,
    [applications, selectedApplicationId],
  );
  const unboundDeviceCount = useMemo(() => devices.filter((item) => !item.agentApplicationId).length, [devices]);
  const runtimeDiagnosticCounts = useMemo(
    () =>
      devices.reduce<Record<DeviceRuntimeDiagnostic['level'], number>>(
        (counts, device) => {
          const diagnostic = resolveDeviceRuntimeDiagnostic(device);
          counts[diagnostic.level] += 1;
          return counts;
        },
        { ready: 0, warning: 0, blocked: 0, offline: 0 },
      ),
    [devices],
  );

  const loadApplicationConfigOptions = async () => {
    const commandGroupsResult = await fetchCommandGroups({ pageSize: 100 });
    setCommandGroupOptions(toSelectOptions(commandGroupsResult.results));
  };

  const loadData = async (query: DeviceListQuery = filters, page = devicePage) => {
    setLoading(true);
    try {
      const [deviceResponse, statsResponse, groupResponse, applicationResponse, agentApplicationResponse] = await Promise.all([
        fetchDevices({ ...query, keyword, page }),
        fetchDeviceStats(),
        fetchDeviceGroups(),
        fetchDeviceApplications(),
        fetchAgentApplications({ page: 1 }),
      ]);
      setDevices(deviceResponse.results);
      setDeviceTotal(deviceResponse.count);
      setDevicePage(page);
      setStats(statsResponse);
      setGroups(groupResponse.results);
      setApplications(applicationResponse.results);
      setAgentApplications(agentApplicationResponse.results);
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
    devicePageRef.current = devicePage;
  }, [devicePage]);

  useEffect(() => {
    if (!canUseDeviceWorkspace) {
      return;
    }
    if (hasLoadedRef.current) {
      return;
    }
    hasLoadedRef.current = true;
    void loadData();
    void loadApplicationConfigOptions();
  }, [canUseDeviceWorkspace]);

  useEffect(() => {
    if (!canUseDeviceWorkspace || !token || (isTenantScopedRoute && realtimeTenantId == null)) {
      setRealtimeConnected(false);
      return undefined;
    }

    let closed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let subscriptionId: string | null = null;

    const scheduleReload = () => {
      if (realtimeRefreshTimerRef.current != null) {
        window.clearTimeout(realtimeRefreshTimerRef.current);
      }
      realtimeRefreshTimerRef.current = window.setTimeout(() => {
        realtimeRefreshTimerRef.current = null;
        void loadDataRef.current?.(filtersRef.current, devicePageRef.current);
      }, 250);
    };

    const connect = () => {
      const nextSubscriptionId = createRealtimeCommandId('devices-sub');
      subscriptionId = nextSubscriptionId;
      socket = new WebSocket(buildRealtimeWebSocketUrl());
      socket.onopen = () => {
        socket?.send(
          encodeRealtimeCommand({
            type: 'devices.events.subscribe',
            id: nextSubscriptionId,
            payload: {
              token,
              ...(realtimeTenantId != null ? { tenantId: realtimeTenantId } : {}),
            },
          }),
        );
      };
      socket.onmessage = (event) => {
        const messageEnvelope = parseRealtimeMessage(event.data);
        if (!messageEnvelope?.type) {
          return;
        }
        if (messageEnvelope.type === 'devices.events.subscribed' && messageEnvelope.id === subscriptionId) {
          setRealtimeConnected(true);
          return;
        }
        if (messageEnvelope.type === 'devices.event') {
          if (
            isDeviceRealtimePayload(messageEnvelope.payload) &&
            messageEnvelope.payload.type.startsWith('device.')
          ) {
            scheduleReload();
          }
          return;
        }
        if (messageEnvelope.type === 'error' && messageEnvelope.id === subscriptionId) {
          setRealtimeConnected(false);
          socket?.close();
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

    setRealtimeConnected(false);
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
      if (socket?.readyState === WebSocket.OPEN && subscriptionId) {
        socket.send(encodeRealtimeCommand(buildDeviceEventsUnsubscribeCommand(createRealtimeCommandId('devices-unsub'))));
      }
      socket?.close();
    };
  }, [canUseDeviceWorkspace, isTenantScopedRoute, realtimeTenantId, token]);

  const handleSearch = () => {
    void loadData(filters, 1);
  };

  const handleFilterChange = <K extends keyof DeviceListQuery>(key: K, value: DeviceListQuery[K]) => {
    const nextFilters = { ...filters, [key]: value };
    setFilters(nextFilters);
    void loadData(nextFilters, 1);
  };

  const openDeviceEdit = (record: DeviceRecord) => {
    setEditingDevice(record);
    deviceForm.setFieldsValue({
      applicationId: record.applicationId ?? null,
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

  const handleDeviceDelete = async (record: DeviceRecord) => {
    await deleteDevice(record.deviceCode);
    message.success('设备已删除');
    void loadData(filters, devicePage);
  };

  const openApplicationCreate = () => {
    setEditingApplication(null);
    applicationForm.resetFields();
    applicationForm.setFieldsValue({
      isActive: true,
      agentApplicationId: null,
      commandGroupIds: [],
    });
    setApplicationModalOpen(true);
  };

  const openApplicationConfig = (record: DeviceApplicationRecord) => {
    setSelectedApplicationId(record.id);
    setEditingApplication(record);
    applicationForm.setFieldsValue({
      name: record.name,
      description: record.description,
      isActive: record.isActive,
      agentApplicationId: record.agentApplicationId ?? null,
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
      const created = await createDeviceApplication({ ...values, code: buildGeneratedApplicationCode() });
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
      title: '绑定智能体',
      dataIndex: 'agentApplicationName',
      key: 'agentApplicationName',
      width: '10%',
      render: (value: string) => (value ? <Tag color="purple">{value}</Tag> : <Tag color="warning">待绑定智能体</Tag>),
    },
    {
      title: '运行诊断',
      key: 'runtimeDiagnostic',
      width: '11%',
      render: (_, record) => {
        const diagnostic = resolveDeviceRuntimeDiagnostic(record);
        return (
          <Tooltip
            title={
              <div>
                <div>{diagnostic.detail}</div>
                <div className="mt-1">下一步：{diagnostic.hint}</div>
              </div>
            }
          >
            <Tag color={diagnostic.color}>{diagnostic.label}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '资源应用',
      dataIndex: 'applicationName',
      key: 'applicationName',
      width: '10%',
      render: (value: string) => (value ? <Tag color="cyan">{value}</Tag> : <Tag color="default">未绑定资源</Tag>),
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
      width: '12%',
      render: (_, record) => (
        <Space size={6}>
          {canUpdateDevice ? (
            <Tooltip title="绑定资源应用">
              <Button size="small" icon={<LinkOutlined />} onClick={() => openDeviceEdit(record)}>
                绑定
              </Button>
            </Tooltip>
          ) : null}
          {canDeleteDevice ? (
            <Popconfirm
              title="删除设备"
              description={`确认删除「${record.name || record.deviceCode}」？同设备码再次上报后会重新进入待绑定。`}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void handleDeviceDelete(record)}
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

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Typography.Text className="!font-medium !text-slate-700">运行链路诊断</Typography.Text>
            <div className="mt-1 text-xs text-slate-500">
              先看授权与智能体绑定，再看在线心跳与资源包；异常联调时让安卓端带回 requestId / traceId。
            </div>
          </div>
          <Space size={[8, 8]} wrap>
            <Tag color={realtimeConnected ? 'success' : 'default'}>
              {realtimeConnected ? '实时通道正常' : '实时通道未连接'}
            </Tag>
            <Tag color="success">就绪 {runtimeDiagnosticCounts.ready}</Tag>
            <Tag color="error">阻塞 {runtimeDiagnosticCounts.blocked}</Tag>
            <Tag color="default">离线 {runtimeDiagnosticCounts.offline}</Tag>
            <Tag color="warning">无资源包 {runtimeDiagnosticCounts.warning}</Tag>
          </Space>
        </div>
      </Card>

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
                    onChange={(value) => handleFilterChange('status', value)}
                    options={[
                      { label: '全部状态', value: 'all' },
                      { label: '在线', value: 'online' },
                      { label: '离线', value: 'offline' },
                    ]}
                  />
                  <Select
                    value={filters.enabledStatus}
                    onChange={(value) => handleFilterChange('enabledStatus', value)}
                    options={[
                      { label: '全部授权', value: 'all' },
                      { label: '正常', value: 'enabled' },
                      { label: '停用', value: 'disabled' },
                    ]}
                  />
                  <Select
                    value={filters.applicationId}
                    onChange={(value) => handleFilterChange('applicationId', value)}
                    options={[{ label: '全部资源应用', value: 'all' }, ...applicationOptions]}
                  />
                  <Select
                    value={filters.groupId}
                    onChange={(value) => handleFilterChange('groupId', value)}
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
                  pagination={{
                    current: devicePage,
                    pageSize: 10,
                    total: deviceTotal,
                    showSizeChanger: false,
                    onChange: (page) => void loadData(filters, page),
                  }}
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
                              </div>
                              <Tag color={item.isActive ? 'success' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
                            </div>
                            <Typography.Paragraph className="!mb-0 !min-h-[40px] !text-[13px] !text-slate-500">
                              {item.description || '未填写说明'}
                            </Typography.Paragraph>
                            <Space size={[4, 4]} wrap>
                              <Tag color={item.agentApplicationId ? 'purple' : 'warning'}>
                                {item.agentApplicationName || '待绑定智能体'}
                              </Tag>
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
                        <Typography.Text type="secondary">当前应用绑定概览</Typography.Text>
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
                        ['智能体', selectedApplication.agentApplicationName || '未绑定', '应用运行时使用的智能体'],
                        ['指令组', selectedApplication.commandGroupIds.length, '控制与任务指令'],
                      ].map(([label, count, desc]) => (
                        <Col xs={24} md={12} key={label}>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                            <Typography.Text type="secondary">{label}</Typography.Text>
                            <div className="mt-1 truncate text-2xl font-semibold tabular-nums">{count}</div>
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
          <Form.Item label="资源应用" name="applicationId">
            <Select options={[...emptyApplicationOption, ...applicationOptions]} optionFilterProp="label" showSearch />
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
        width="42vw"
      >
        <Form<ApplicationForm> form={applicationForm} layout="vertical">
          <Form.Item label="应用名称" name="name" rules={[{ required: true, message: '请输入应用名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item label="启用应用" name="isActive" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="绑定智能体" name="agentApplicationId">
            <Select options={[...emptyAgentApplicationOption, ...agentApplicationOptions]} optionFilterProp="label" showSearch />
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
