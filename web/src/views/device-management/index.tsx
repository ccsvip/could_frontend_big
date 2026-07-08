import {
  IconApps,
  IconMicrophone,
  IconTrash,
  IconDeviceDesktop,
  IconEdit,
  IconPlus,
  IconReload,
  IconSearch,
  IconSettings,
} from '@tabler/icons-react';
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
import { useLocation, useSearchParams } from 'react-router-dom';
import {
  buildDeviceEventsUnsubscribeCommand,
  buildRealtimeWebSocketUrl,
  createRealtimeCommandId,
  encodeRealtimeCommand,
  parseRealtimeMessage,
} from '../../api/realtime';
import {
  createDeviceApplication,
  createWakeWord,
  deleteDevice,
  deleteWakeWord,
  fetchDeviceApplications,
  fetchDeviceStats,
  fetchWakeWords,
  fetchDevices,
  updateDevice,
  updateDeviceApplication,
  updateWakeWord,
  type DeviceApplicationPayload,
  type DeviceApplicationRecord,
  type DeviceAuthorizationType,
  type DeviceListQuery,
  type DeviceRecord,
  type WakeWordPayload,
  type WakeWordRecord,
} from '../../api/modules/devices';
import { fetchCommandGroups } from '../../api/modules/commands';
import { fetchAgentApplications, type AgentApplicationRecord } from '../../api/modules/applications';
import { fetchCompanyTtsOptions } from '../../api/modules/tts';
import { useAuthStore } from '../../store/auth';
import { useTenantScopeStore } from '../../store/tenant-scope';

type DeviceEditForm = {
  name: string;
  applicationId?: number | null;
  voiceToneId?: number | null;
};

type ApplicationForm = DeviceApplicationPayload;
type WakeWordForm = WakeWordPayload;

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
const emptyVoiceToneOption = [{ label: '暂不绑定音色', value: null as number | null }];

type DeviceWakeWordRow = {
  device: DeviceRecord;
  wakeWords: WakeWordRecord[];
};

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [deviceTotal, setDeviceTotal] = useState(0);
  const [devicePage, setDevicePage] = useState(1);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, trial: 0, permanent: 0 });
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [wakeWords, setWakeWords] = useState<WakeWordRecord[]>([]);
  const [agentApplications, setAgentApplications] = useState<AgentApplicationRecord[]>([]);
  const [commandGroupOptions, setCommandGroupOptions] = useState<ResourceOption[]>([]);
  const [voiceToneOptions, setVoiceToneOptions] = useState<ResourceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [filters, setFilters] = useState<DeviceListQuery>({
    status: 'all',
    enabledStatus: 'all',
    applicationId: 'all',
  });
  const [editingDevice, setEditingDevice] = useState<DeviceRecord | null>(null);
  const [editingApplication, setEditingApplication] = useState<DeviceApplicationRecord | null>(null);
  const [editingWakeWord, setEditingWakeWord] = useState<WakeWordRecord | null>(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | null>(null);
  const [realtimeConnected, setRealtimeConnected] = useState(false);
  const [applicationModalOpen, setApplicationModalOpen] = useState(false);
  const [wakeWordModalOpen, setWakeWordModalOpen] = useState(false);
  const [selectedWakeWordDeviceId, setSelectedWakeWordDeviceId] = useState<number | null>(null);
  const [deviceForm] = Form.useForm<DeviceEditForm>();
  const [applicationForm] = Form.useForm<ApplicationForm>();
  const [wakeWordForm] = Form.useForm<WakeWordForm>();
  const hasLoadedRef = useRef(false);
  const filtersRef = useRef(filters);
  const devicePageRef = useRef(devicePage);
  const realtimeRefreshTimerRef = useRef<number | null>(null);
  const loadDataRef = useRef<((query?: DeviceListQuery, page?: number) => Promise<void>) | null>(null);
  const { pathname } = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
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

  const applicationOptions = useMemo(() => toSelectOptions(applications), [applications]);
  const deviceOptions = useMemo(() => devices.map((item) => ({ label: `${item.name}（${item.deviceCode}）`, value: item.recordId })), [devices]);
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

  const tabParam = searchParams.get('tab');
  const activeTabKey = tabParam === 'applications' || tabParam === 'wakeWords' ? tabParam : 'devices';

  const deviceWakeWordRows = useMemo<DeviceWakeWordRow[]>(() => {
    const wakeWordsByDeviceId = new Map<number, WakeWordRecord[]>();
    wakeWords.forEach((wakeWord) => {
      const deviceIds = wakeWord.deviceIds?.length ? wakeWord.deviceIds : wakeWord.devices.map((device) => device.id);
      deviceIds.forEach((deviceId) => {
        const items = wakeWordsByDeviceId.get(deviceId) ?? [];
        items.push(wakeWord);
        wakeWordsByDeviceId.set(deviceId, items);
      });
    });
    return devices.map((device) => ({ device, wakeWords: wakeWordsByDeviceId.get(device.recordId) ?? [] }));
  }, [devices, wakeWords]);

  const selectedDeviceWakeWordRow = useMemo(
    () =>
      deviceWakeWordRows.find((item) => item.device.recordId === selectedWakeWordDeviceId) ??
      deviceWakeWordRows[0] ??
      null,
    [deviceWakeWordRows, selectedWakeWordDeviceId],
  );

  const loadApplicationConfigOptions = async () => {
    const commandGroupsResult = await fetchCommandGroups({ pageSize: 100 });
    setCommandGroupOptions(toSelectOptions(commandGroupsResult.results));
  };

  const refreshVoiceToneOptions = async () => {
    const ttsOptionsResponse = await fetchCompanyTtsOptions();
    const nextOptions = ttsOptionsResponse.voices.map((item) => ({ label: `${item.displayName}（${item.voiceCode}）`, value: item.id }));
    setVoiceToneOptions(nextOptions);
    return nextOptions;
  };

  const loadData = async (query: DeviceListQuery = filters, page = devicePage) => {
    setLoading(true);
    try {
      const [deviceResponse, statsResponse, applicationResponse, agentApplicationResponse, wakeWordResponse, nextVoiceToneOptions] = await Promise.all([
        fetchDevices({ ...query, keyword, page }),
        fetchDeviceStats(),
        fetchDeviceApplications(),
        fetchAgentApplications({ page: 1 }),
        fetchWakeWords({ keyword: keyword || undefined }),
        refreshVoiceToneOptions().catch(() => []),
      ]);
      setDevices(deviceResponse.results);
      setDeviceTotal(deviceResponse.count);
      setDevicePage(page);
      setStats(statsResponse);
      setApplications(applicationResponse.results);
      setAgentApplications(agentApplicationResponse.results);
      setWakeWords(wakeWordResponse.results);
      setVoiceToneOptions(nextVoiceToneOptions);
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

  const handleMainTabChange = (key: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (key === 'devices') {
      nextParams.delete('tab');
    } else {
      nextParams.set('tab', key);
    }
    setSearchParams(nextParams, { replace: true });
  };


  const openDeviceEdit = async (record: DeviceRecord) => {
    try {
      await refreshVoiceToneOptions();
    } catch {
      message.warning('音色列表刷新失败，将使用当前已加载的选项');
    }
    setEditingDevice(record);
    deviceForm.setFieldsValue({
      name: record.name,
      applicationId: record.applicationId ?? null,
      voiceToneId: record.voiceToneId ?? null,
    });
  };

  const handleDeviceSave = async () => {
    if (!editingDevice) return;
    const values = await deviceForm.validateFields();
    const nextDevice = await updateDevice(editingDevice.deviceCode, values);
    setDevices((current) => current.map((item) => (item.deviceCode === nextDevice.deviceCode ? nextDevice : item)));
    setEditingDevice(null);
    message.success('设备信息已更新');
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


  const openWakeWordModal = (record?: WakeWordRecord, presetDeviceId?: number) => {
    setEditingWakeWord(record ?? null);
    wakeWordForm.setFieldsValue({
      text: record?.text ?? '',
      boost: record?.boost ?? 2.0,
      threshold: record?.threshold ?? 0.25,
      isActive: record?.isActive ?? true,
      deviceIds: record?.deviceIds ?? (presetDeviceId ? [presetDeviceId] : []),
    });
    setWakeWordModalOpen(true);
  };

  const handleWakeWordSave = async () => {
    const values = await wakeWordForm.validateFields();
    if (editingWakeWord) {
      await updateWakeWord(editingWakeWord.id, values);
      message.success('唤醒词已更新');
    } else {
      await createWakeWord(values);
      message.success('唤醒词已创建');
    }
    setWakeWordModalOpen(false);
    await loadData(filters, devicePage);
  };

  const handleWakeWordDelete = async (record: WakeWordRecord) => {
    await deleteWakeWord(record.id);
    message.success('唤醒词已删除');
    await loadData(filters, devicePage);
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
        <Typography.Text className="text-xs" copyable>
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
      title: '当前音色',
      dataIndex: 'voiceToneName',
      key: 'voiceToneName',
      width: '10%',
      render: (value: string, record) => (value ? <Tag color="blue">{record.voiceToneCode || value}</Tag> : <Tag color="default">未绑定音色</Tag>),
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
            <Tooltip title="编辑设备名称和资源应用">
              <Button size="small" icon={<IconEdit />} onClick={() => { void openDeviceEdit(record); }}>
                编辑
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
              <Button size="small" danger icon={<IconTrash />}>
                删除
              </Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  const renderWakeWordActions = (wakeWord: WakeWordRecord) => (
    <Space size={6}>
      {canUpdateDevice ? (
        <Button size="small" icon={<IconEdit size={14} />} onClick={() => openWakeWordModal(wakeWord)}>
          编辑
        </Button>
      ) : null}
      {canDeleteDevice ? (
        <Popconfirm title="确认删除该唤醒词？" onConfirm={() => handleWakeWordDelete(wakeWord)}>
          <Button size="small" danger icon={<IconTrash size={14} />}>
            删除
          </Button>
        </Popconfirm>
      ) : null}
    </Space>
  );

  const renderWakeWordPills = (items: WakeWordRecord[]) => {
    if (!items.length) {
      return <Tag color="warning">未添加唤醒词</Tag>;
    }
    return (
      <Space size={[6, 6]} wrap>
        {items.map((item) => (
          <Tag key={item.id} color={item.isActive ? 'success' : 'default'} className="rounded-full px-3 py-1 text-sm">
            {item.text}
          </Tag>
        ))}
      </Space>
    );
  };

  const renderDeviceIdentity = (device: DeviceRecord) => (
    <Space direction="vertical" size={2} className="min-w-0">
      <Typography.Text strong className="truncate text-slate-900">
        {device.name || device.deviceCode}
      </Typography.Text>
      <Typography.Text className="text-xs text-slate-500">{device.deviceCode}</Typography.Text>
    </Space>
  );

  const renderDeviceRuntimeTags = (device: DeviceRecord) => {
    const diagnostic = resolveDeviceRuntimeDiagnostic(device);
    return (
      <Space size={[4, 4]} wrap>
        <Tag color={statusMap[device.status].color}>{statusMap[device.status].text}</Tag>
        <Tag color={diagnostic.color}>{diagnostic.label}</Tag>
      </Space>
    );
  };

  const renderWakeWordPhraseList = (items: WakeWordRecord[], emptyDescription: string, presetDeviceId?: number) => {
    if (!items.length) {
      return (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center">
          <Typography.Text type="secondary">{emptyDescription}</Typography.Text>
          {canCreateDevice ? (
            <div className="mt-3">
              <Button icon={<IconPlus size={14} />} onClick={() => openWakeWordModal(undefined, presetDeviceId)}>
                添加唤醒词
              </Button>
            </div>
          ) : null}
        </div>
      );
    }

    return (
      <Space direction="vertical" size={8} className="w-full">
        {items.map((wakeWord) => (
          <div key={wakeWord.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <Typography.Text strong className="text-base text-slate-900">
                {wakeWord.text}
              </Typography.Text>
            </div>
            {renderWakeWordActions(wakeWord)}
          </div>
        ))}
      </Space>
    );
  };

  const renderWakeWordsHeader = () => {
    const configuredDeviceCount = deviceWakeWordRows.filter((item) => item.wakeWords.length > 0).length;
    const activeWakeWordCount = wakeWords.filter((item) => item.isActive).length;
    return (
      <Card className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <Typography.Title level={4} className="mb-1 flex items-center gap-2">
              <IconMicrophone size={22} /> 按设备查看唤醒词
            </Typography.Title>
            <Typography.Text type="secondary">
              只展示用户添加的中文唤醒词，按设备确认哪些已经配置、哪些还需要补齐。
            </Typography.Text>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:min-w-[24rem]">
            {[
              ['设备', deviceWakeWordRows.length, 'text-slate-900'],
              ['已配置', configuredDeviceCount, 'text-brand-700'],
              ['唤醒词', activeWakeWordCount, 'text-sky-700'],
            ].map(([label, value, color]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-xs text-slate-500">{label}</div>
                <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
              </div>
            ))}
          </div>
          {canCreateDevice ? (
            <Button type="primary" icon={<IconPlus size={16} />} onClick={() => openWakeWordModal()}>
              新建唤醒词
            </Button>
          ) : null}
        </div>
      </Card>
    );
  };

  const renderWakeWordsByDevice = () => {
    const selectedRow = selectedDeviceWakeWordRow;
    const selectedDeviceId = selectedRow?.device.recordId ?? null;
    return (
      <Space direction="vertical" size={16} className="w-full">
        {renderWakeWordsHeader()}
        {deviceWakeWordRows.length === 0 ? (
          <Empty description="暂无设备" />
        ) : (
          <div className="grid gap-3 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
            <Card className="rounded-xl border border-slate-200/70 shadow-card">
              <Space direction="vertical" size={8} className="w-full">
                <Typography.Text strong>选择设备</Typography.Text>
                {deviceWakeWordRows.map((row) => {
                  const active = row.device.recordId === selectedDeviceId;
                  return (
                    <button
                      key={row.device.recordId}
                      type="button"
                      className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                        active ? 'border-brand-200 bg-brand-50' : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                      onClick={() => setSelectedWakeWordDeviceId(row.device.recordId)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-slate-900">{row.device.name || row.device.deviceCode}</span>
                        <Tag color={row.wakeWords.length ? 'success' : 'warning'}>{row.wakeWords.length} 个</Tag>
                      </div>
                      <div className="mt-2">{renderWakeWordPills(row.wakeWords.slice(0, 3))}</div>
                    </button>
                  );
                })}
              </Space>
            </Card>
            <Card className="rounded-xl border border-slate-200/70 shadow-card">
              {selectedRow ? (
                <Space direction="vertical" size={16} className="w-full">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>{renderDeviceIdentity(selectedRow.device)}</div>
                    <Space size={[6, 6]} wrap>
                      {renderDeviceRuntimeTags(selectedRow.device)}
                      {canCreateDevice ? (
                        <Button icon={<IconPlus size={14} />} onClick={() => openWakeWordModal(undefined, selectedRow.device.recordId)}>
                          添加唤醒词
                        </Button>
                      ) : null}
                    </Space>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <Typography.Title level={5} className="mb-3">
                      当前设备唤醒词
                    </Typography.Title>
                    {renderWakeWordPhraseList(selectedRow.wakeWords, '这台设备还没有添加唤醒词', selectedRow.device.recordId)}
                  </div>
                </Space>
              ) : (
                <Empty description="请选择设备" />
              )}
            </Card>
          </div>
        )}
      </Space>
    );
  };

  if (!canUseDeviceWorkspace) {
    return <Empty description="请先进入公司租户范围后再管理设备、应用和唤醒词" />;
  }

  return (
    <Space direction="vertical" size={16} className="w-full">
      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Tag color={realtimeConnected ? 'success' : 'default'}>
                {realtimeConnected ? '实时同步中' : '实时未连接'}
              </Tag>
              <Tag color="success">就绪 {runtimeDiagnosticCounts.ready}</Tag>
              <Tag color="error">阻塞 {runtimeDiagnosticCounts.blocked}</Tag>
              <Tag color="default">离线 {runtimeDiagnosticCounts.offline}</Tag>
              <Tag color="warning">无资源包 {runtimeDiagnosticCounts.warning}</Tag>
            </div>
            <Typography.Title level={4} className="mb-1 font-semibold text-slate-900">
              设备与应用
            </Typography.Title>
            <Typography.Text className="text-[13px] text-slate-500">
              设备码、授权状态、资源应用和智能体运行链路集中维护。
            </Typography.Text>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[34rem]">
            {[
              ['设备总数', stats.total, 'text-slate-900'],
              ['在线', stats.online, 'text-brand-700'],
              ['待绑定', unboundDeviceCount, 'text-amber-600'],
              ['应用数', applications.length, 'text-sky-700'],
            ].map(([label, value, color]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-xs text-slate-500">{label}</div>
                <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
              </div>
            ))}
          </div>
          <Button icon={<IconReload />} onClick={() => loadData()}>
            刷新
          </Button>
        </div>
      </Card>

      <Tabs
        activeKey={activeTabKey}
        onChange={handleMainTabChange}
        items={[
          {
            key: 'devices',
            label: (
              <Space size={6}>
                <IconDeviceDesktop />
                设备
              </Space>
            ),
            children: (
              <Space direction="vertical" size={12} className="w-full">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(220px,1fr)_140px_140px_160px_auto]">
                  <Input
                    value={keyword}
                    prefix={<IconSearch />}
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
                  <Button type="primary" icon={<IconSearch />} onClick={handleSearch}>
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
                <IconApps />
                应用
              </Space>
            ),
            children: (
              <Space direction="vertical" size={14} className="w-full">
                <div className="flex justify-end">
                  {canCreateDevice ? (
                    <Button type="primary" icon={<IconPlus />} onClick={openApplicationCreate}>
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
                          className={`h-full rounded-xl border shadow-card ${
                            selectedApplication?.id === item.id ? 'border-brand-300' : 'border-slate-200/70'
                          }`}
                          onClick={() => setSelectedApplicationId(item.id)}
                        >
                          <Space direction="vertical" size={10} className="w-full">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <Typography.Title level={5} className="mb-1 truncate">
                                  {item.name}
                                </Typography.Title>
                              </div>
                              <Tag color={item.isActive ? 'success' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
                            </div>
                            <Typography.Paragraph className="mb-0 min-h-[40px] text-[13px] text-slate-500">
                              {item.description || '未填写说明'}
                            </Typography.Paragraph>
                            <Space size={[4, 4]} wrap>
                              <Tag color={item.agentApplicationId ? 'purple' : 'warning'}>
                                {item.agentApplicationName || '待绑定智能体'}
                              </Tag>
                              <Tag>指令 {item.commandGroupIds.length}</Tag>
                            </Space>
                            {canUpdateDevice ? (
                              <Button icon={<IconSettings />} onClick={() => openApplicationConfig(item)}>
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
                        <Typography.Title level={5} className="mb-1">
                          {selectedApplication.name}
                        </Typography.Title>
                        <Typography.Text type="secondary">当前应用绑定概览</Typography.Text>
                      </div>
                      {canUpdateDevice ? (
                        <Button icon={<IconSettings />} onClick={() => openApplicationConfig(selectedApplication)}>
                          打开配置
                        </Button>
                      ) : null}
                    </div>
                    <Divider className="my-4" />
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
            key: 'wakeWords',
            label: (
              <Space size={6}>
                <IconMicrophone />
                唤醒词
              </Space>
            ),
            children: renderWakeWordsByDevice(),
          },
        ]}
      />

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
          <Form.Item
            label="设备名称"
            name="name"
            extra="保存后会同步到设备运行时配置 device.name。"
            rules={[{ required: true, whitespace: true, message: '请输入设备名称' }]}
          >
            <Input placeholder="请输入设备名称" />
          </Form.Item>
          <Form.Item label="资源应用" name="applicationId">
            <Select options={[...emptyApplicationOption, ...applicationOptions]} optionFilterProp="label" showSearch />
          </Form.Item>
          <Form.Item label="当前音色" name="voiceToneId" extra="运行时配置只会返回该设备当前绑定的音色。">
            <Select options={[...emptyVoiceToneOption, ...voiceToneOptions]} optionFilterProp="label" showSearch />
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
        title={editingWakeWord ? '编辑唤醒词' : '新建唤醒词'}
        open={wakeWordModalOpen}
        onCancel={() => setWakeWordModalOpen(false)}
        onOk={handleWakeWordSave}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
        width={720}
      >
        <Form<WakeWordForm> form={wakeWordForm} layout="vertical">
          <Form.Item
            label="中文唤醒词"
            name="text"
            extra="必须以“你好”开头，总长 4-6 个汉字（含“你好”）。"
            rules={[{ required: true, message: '请输入中文唤醒词' }]}
          >
            <Input placeholder="例如：你好小德" />
          </Form.Item>
          <Form.Item name="boost" initialValue={2.0} hidden>
            <Input type="hidden" />
          </Form.Item>
          <Form.Item name="threshold" initialValue={0.25} hidden>
            <Input type="hidden" />
          </Form.Item>
          <Form.Item label="启用唤醒词" name="isActive" valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>
          <Form.Item label="绑定设备" name="deviceIds" extra="一个唤醒词可以绑定多个同公司设备。">
            <Select mode="multiple" options={deviceOptions} optionFilterProp="label" placeholder="请选择设备" />
          </Form.Item>
        </Form>
      </Modal>

    </Space>
  );
};
