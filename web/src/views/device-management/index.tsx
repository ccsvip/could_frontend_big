import {
  IconApps,
  IconMicrophone,
  IconDeviceDesktop,
  IconEdit,
  IconPlus,
  IconReload,
  IconSearch,
  IconSettings,
  IconTrash,
} from '@tabler/icons-react';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
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
  deleteDeviceApplication,
  createWakeWord,
  deleteWakeWord,
  fetchDeviceApplications,
  fetchDeviceApplicationDeletionImpact,
  fetchDeviceStats,
  fetchWakeWords,
  fetchDevices,
  updateDevice,
  updateDeviceApplication,
  updateWakeWord,
  type DeviceApplicationPayload,
  type DeviceApplicationRecord,
  type DeviceListQuery,
  type DeviceRecord,
  type DeviceVoiceToneConfig,
  type WakeWordPayload,
  type WakeWordRecord,
} from '../../api/modules/devices';
import { fetchCommandGroups } from '../../api/modules/commands';
import { fetchAgentApplications, type AgentApplicationRecord } from '../../api/modules/applications';
import { fetchCompanyTtsOptions } from '../../api/modules/tts';
import { useAuthStore } from '../../store/auth';
import { useTenantScopeStore } from '../../store/tenant-scope';
import { resolveDeviceExpirationDisplay } from './device-expiration-display';

type DeviceEditForm = {
  name: string;
  applicationId?: number | null;
  voiceToneId?: number | null;
  voiceToneConfig: DeviceVoiceToneConfig;
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

const toSelectOptions = <T extends { id: number; name: string }>(items: T[]) =>
  items.map((item) => ({ label: item.name, value: item.id }));

const buildGeneratedApplicationCode = () => `device-app-${Date.now().toString(36)}`;

const isDeviceRealtimePayload = (payload: unknown): payload is { type: string } =>
  !!payload && typeof payload === 'object' && typeof (payload as { type?: unknown }).type === 'string';

const emptyApplicationOption = [{ label: '待绑定资源应用', value: null as number | null }];
const emptyAgentApplicationOption = [{ label: '待绑定智能体', value: null as number | null }];
const emptyVoiceToneOption = [{ label: '暂不绑定音色', value: null as number | null }];
const DEFAULT_VOICE_TONE_CONFIG: DeviceVoiceToneConfig = {
  speechRate: 1,
  pitchRate: 1,
  volume: 50,
};

type DeviceWakeWordRow = {
  device: DeviceRecord;
  wakeWords: WakeWordRecord[];
};

export const DeviceManagementPage = () => {
  const [devices, setDevices] = useState<DeviceRecord[]>([]);
  const [devicePage, setDevicePage] = useState(1);
  const [stats, setStats] = useState({ total: 0, online: 0, offline: 0, trial: 0, permanent: 0 });
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [wakeWords, setWakeWords] = useState<WakeWordRecord[]>([]);
  const [agentApplications, setAgentApplications] = useState<AgentApplicationRecord[]>([]);
  const [commandGroupOptions, setCommandGroupOptions] = useState<ResourceOption[]>([]);
  const [voiceToneOptions, setVoiceToneOptions] = useState<ResourceOption[]>([]);
  const [defaultVoiceToneConfig, setDefaultVoiceToneConfig] = useState<DeviceVoiceToneConfig>(DEFAULT_VOICE_TONE_CONFIG);
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
  const [selectedDeviceCode, setSelectedDeviceCode] = useState<string | null>(null);
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
  const unboundDeviceCount = useMemo(() => devices.filter((item) => !item.agentApplicationId).length, [devices]);
  const selectedDevice = useMemo(() => devices.find((d) => d.deviceCode === selectedDeviceCode) ?? null, [devices, selectedDeviceCode]);
  const selectedDeviceExpiration = selectedDevice ? resolveDeviceExpirationDisplay(selectedDevice) : null;
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

  const handleApplicationDelete = async (record: DeviceApplicationRecord) => {
    const impact = await fetchDeviceApplicationDeletionImpact(record.id);
    Modal.confirm({
      title: `删除应用「${record.name}」`,
      content: (
        <div className="space-y-2 text-fluid-base text-slate-600">
          <p>将解除 {impact.deviceCount} 台设备的应用绑定。</p>
          <p>{impact.authorizationCodeCount} 条历史授权码将变为未分配状态。</p>
          <p>设备需要重新绑定应用；授权码需要重新分配应用后才能恢复关联。</p>
        </div>
      ),
      okText: '删除应用',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteDeviceApplication(record.id);
        setApplications((current) => current.filter((item) => item.id !== record.id));
        setSelectedApplicationId((current) => (current === record.id ? null : current));
        message.success('应用已删除');
        await loadDataRef.current?.(filtersRef.current, devicePageRef.current);
      },
    });
  };

  const applicationColumns = useMemo(() => {
    type R = DeviceApplicationRecord;
    return [
      {
        title: '应用名称',
        dataIndex: 'name',
        key: 'name',
        width: 200,
        render: (name: string) => (
          <span className="font-medium text-slate-800">{name}</span>
        ),
      },
      {
        title: '状态',
        dataIndex: 'isActive',
        key: 'isActive',
        width: 80,
        render: (active: boolean) => (
          <Tag color={active ? 'success' : 'default'}>{active ? '启用' : '停用'}</Tag>
        ),
      },
      {
        title: '智能体',
        dataIndex: 'agentApplicationName',
        key: 'agent',
        width: 180,
        render: (name: string | null, record: R) => (
          <Tag color={record.agentApplicationId ? 'purple' : 'warning'}>
            {name || '待绑定智能体'}
          </Tag>
        ),
      },
      {
        title: '指令',
        key: 'commands',
        width: 80,
        render: (_: unknown, record: R) => (
          <span className="tabular-nums text-slate-600">{record.commandGroupIds.length}</span>
        ),
      },
      {
        title: '说明 / 更新时间',
        key: 'meta',
        width: 240,
        render: (_: unknown, record: R) => (
          <div className="flex flex-col gap-0.5">
            <div className="truncate text-fluid-base text-slate-600">
              {record.description || <span className="italic text-slate-400">未填写说明</span>}
            </div>
            <div className="text-fluid-xs text-slate-400 tabular-nums">
              {record.updated_at ?? '-'}
            </div>
          </div>
        ),
      },
      {
        title: '操作',
        key: 'actions',
        width: 100,
        render: (_: unknown, record: R) =>
          canUpdateDevice || canDeleteDevice ? (
            <Space size={8}>
              {canUpdateDevice ? (
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-fluid-sm text-slate-600 transition hover:bg-slate-50 hover:text-brand-700"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    openApplicationConfig(record);
                  }}
                >
                  <IconSettings size={14} />
                  配置
                </button>
              ) : null}
              {canDeleteDevice ? (
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-fluid-sm text-red-600 transition hover:bg-red-50"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    void handleApplicationDelete(record);
                  }}
                >
                  <IconTrash size={14} />
                  删除
                </button>
              ) : null}
            </Space>
          ) : null,
      },
    ];
  }, [canDeleteDevice, canUpdateDevice, handleApplicationDelete]);

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

  const loadApplicationConfigOptions = async () => {
    const commandGroupsResult = await fetchCommandGroups({ pageSize: 100 });
    setCommandGroupOptions(toSelectOptions(commandGroupsResult.results));
  };

  const refreshVoiceToneOptions = async () => {
    const ttsOptionsResponse = await fetchCompanyTtsOptions();
    const sessionConfig = ttsOptionsResponse.ttsSessionConfig;
    setDefaultVoiceToneConfig({
      speechRate: sessionConfig.speech_rate ?? DEFAULT_VOICE_TONE_CONFIG.speechRate,
      pitchRate: sessionConfig.pitch_rate ?? DEFAULT_VOICE_TONE_CONFIG.pitchRate,
      volume: sessionConfig.volume ?? DEFAULT_VOICE_TONE_CONFIG.volume,
    });
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
    if (devices.length > 0 && !selectedDeviceCode) {
      setSelectedDeviceCode(devices[0].deviceCode);
    }
  }, [devices, selectedDeviceCode]);

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
      voiceToneConfig: record.voiceToneConfig ?? defaultVoiceToneConfig,
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

  const renderWakeWordsByDevice = () => (
    <Space direction="vertical" size={16} className="w-full">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Typography.Title level={5} className="mb-0 text-fluid-lg">
          唤醒词管理
        </Typography.Title>
        {canCreateDevice ? (
          <Button type="primary" icon={<IconPlus size={16} />} onClick={() => openWakeWordModal()}>
            新建唤醒词
          </Button>
        ) : null}
      </div>

      {deviceWakeWordRows.length === 0 ? (
        <Typography.Text type="secondary">暂无设备</Typography.Text>
      ) : (
        <Table
          dataSource={deviceWakeWordRows}
          rowKey={(r) => r.device.recordId}
          size="middle"
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 台设备` }}
          scroll={{ x: 800 }}
          expandable={{
            expandedRowRender: (row) => {
              if (!row.wakeWords.length) {
                return (
                  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center">
                    <Typography.Text type="secondary">该设备还没有唤醒词</Typography.Text>
                    {canCreateDevice ? (
                      <div className="mt-3">
                        <Button
                          size="small"
                          icon={<IconPlus size={14} />}
                          onClick={() => openWakeWordModal(undefined, row.device.recordId)}
                        >
                          添加唤醒词
                        </Button>
                      </div>
                    ) : null}
                  </div>
                );
              }
              return (
                <Table
                  dataSource={row.wakeWords}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  showHeader={false}
                  columns={[
                    {
                      title: '唤醒词',
                      dataIndex: 'text',
                      key: 'text',
                      render: (text: string) => (
                        <Typography.Text strong className="text-slate-900">{text}</Typography.Text>
                      ),
                    },
                    {
                      title: '状态',
                      dataIndex: 'isActive',
                      key: 'isActive',
                      width: 80,
                      render: (active: boolean) => (
                        <Tag color={active ? 'success' : 'default'}>{active ? '启用' : '停用'}</Tag>
                      ),
                    },
                    {
                      title: '操作',
                      key: 'actions',
                      width: 140,
                      render: (_: unknown, w: WakeWordRecord) => (
                        <Space size={4}>
                          {canUpdateDevice ? (
                            <Button size="small" icon={<IconEdit size={14} />} onClick={() => openWakeWordModal(w)}>
                              编辑
                            </Button>
                          ) : null}
                          {canDeleteDevice ? (
                            <Popconfirm title="确认删除该唤醒词？" onConfirm={() => handleWakeWordDelete(w)}>
                              <Button size="small" danger icon={<IconTrash size={14} />}>
                                删除
                              </Button>
                            </Popconfirm>
                          ) : null}
                        </Space>
                      ),
                    },
                  ]}
                />
              );
            },
            rowExpandable: () => true,
          }}
          columns={[
            {
              title: '设备名称',
              dataIndex: ['device', 'name'],
              key: 'name',
              width: 200,
              render: (name: string, record: DeviceWakeWordRow) => (
                <Space size={8}>
                  <span
                    className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${
                      record.device.status === 'online' ? 'bg-brand-500' : 'bg-slate-300'
                    }`}
                  />
                  <Typography.Text strong className="text-slate-800">
                    {name || record.device.deviceCode}
                  </Typography.Text>
                </Space>
              ),
            },
            {
              title: '设备码',
              dataIndex: ['device', 'deviceCode'],
              key: 'deviceCode',
              width: 180,
              render: (code: string) => (
                <Typography.Text className="font-mono text-fluid-xs text-slate-500" copyable>
                  {code}
                </Typography.Text>
              ),
            },
            {
              title: '状态',
              key: 'status',
              width: 80,
              render: (_: unknown, record: DeviceWakeWordRow) => (
                <Tag color={statusMap[record.device.status].color}>
                  {statusMap[record.device.status].text}
                </Tag>
              ),
            },
            {
              title: '唤醒词数',
              key: 'count',
              width: 100,
              sorter: (a: DeviceWakeWordRow, b: DeviceWakeWordRow) => a.wakeWords.length - b.wakeWords.length,
              render: (_: unknown, record: DeviceWakeWordRow) => (
                <Tag color={record.wakeWords.length ? 'success' : 'warning'}>
                  {record.wakeWords.length} 个
                </Tag>
              ),
            },
            {
              title: '唤醒词预览',
              key: 'preview',
              render: (_: unknown, record: DeviceWakeWordRow) => {
                if (!record.wakeWords.length) {
                  return <Typography.Text type="secondary" className="text-fluid-xs">—</Typography.Text>;
                }
                return (
                  <Space size={[4, 4]} wrap>
                    {record.wakeWords.map((w) => (
                      <Tag key={w.id} color={w.isActive ? 'success' : 'default'} className="rounded-full">
                        {w.text}
                      </Tag>
                    ))}
                  </Space>
                );
              },
            },
          ]}
        />
      )}
    </Space>
  );

  if (!canUseDeviceWorkspace) {
    return <Empty description="请先进入公司租户范围后再管理设备、应用和唤醒词" />;
  }

  return (
    <Space direction="vertical" size={16} className="w-full">
      <div className="grid w-full gap-5">
      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
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
            <Typography.Title level={4} className="mb-1 font-semibold text-slate-900 text-fluid-xl">
              设备与应用
            </Typography.Title>
            <Typography.Text className="text-fluid-base text-slate-500">
              设备码、授权状态、资源应用和智能体运行链路集中维护。
            </Typography.Text>
          </div>
          <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4 xl:max-w-[34rem]">
            {[
              ['设备总数', stats.total, 'text-slate-900'],
              ['在线', stats.online, 'text-brand-700'],
              ['待绑定', unboundDeviceCount, 'text-amber-600'],
              ['应用数', applications.length, 'text-sky-700'],
            ].map(([label, value, color]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="text-fluid-xs text-slate-500">{label}</div>
                <div className={`mt-1 text-fluid-stat font-semibold tabular-nums ${color}`}>{value}</div>
              </div>
            ))}
          </div>
          <Button className="self-start" icon={<IconReload />} onClick={() => loadData()}>
            刷新
          </Button>
        </div>
      </Card>

      <div className="min-w-0">
      <Tabs
        className="rounded-xl border border-slate-200/70 bg-white px-4 pt-2 shadow-card"
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
              <Space direction="vertical" size={16} className="w-full">
                <div className="flex flex-wrap items-center gap-2 text-fluid-base">
                  <Tag color={realtimeConnected ? 'success' : 'default'}>
                    {realtimeConnected ? '● 实时同步中' : '○ 实时未连接'}
                  </Tag>
                  <span className="text-slate-400">|</span>
                  <span className="text-slate-500">设备 <strong className="text-slate-800">{stats.total}</strong></span>
                  <span className="text-brand-700">在线 <strong>{stats.online}</strong></span>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                  <div className="flex flex-wrap items-end gap-2">
                    <Input
                      className="w-full min-w-[200px] sm:w-auto sm:min-w-[240px] sm:flex-1"
                      value={keyword}
                      prefix={<IconSearch />}
                      placeholder="按设备名称或设备码搜索"
                      onChange={(e) => setKeyword(e.target.value)}
                      onPressEnter={handleSearch}
                    />
                    <Select
                      className="w-full sm:w-[130px]"
                      value={filters.status}
                      onChange={(v) => handleFilterChange('status', v)}
                      options={[
                        { label: '全部状态', value: 'all' },
                        { label: '在线', value: 'online' },
                        { label: '离线', value: 'offline' },
                      ]}
                    />
                    <Select
                      className="w-full sm:w-[120px]"
                      value={filters.enabledStatus}
                      onChange={(v) => handleFilterChange('enabledStatus', v)}
                      options={[
                        { label: '全部授权', value: 'all' },
                        { label: '正常', value: 'enabled' },
                        { label: '停用', value: 'disabled' },
                      ]}
                    />
                    <Select
                      className="w-full min-w-[130px] sm:w-[160px]"
                      value={filters.applicationId}
                      onChange={(v) => handleFilterChange('applicationId', v)}
                      options={[{ label: '全部资源应用', value: 'all' }, ...applicationOptions]}
                    />
                    <Button type="primary" icon={<IconSearch />} onClick={handleSearch}>
                      查询
                    </Button>
                  </div>
                </div>
                {loading ? (
                  <div className="flex items-center justify-center py-20 text-slate-400">加载中...</div>
                ) : devices.length === 0 ? (
                  <Empty description="暂无设备" />
                ) : (
                  <div className="flex h-[clamp(380px,50vh,600px)] gap-4">
                    {/* Left panel */}
                    <div className="flex w-56 shrink-0 flex-col rounded-xl border border-slate-200/70 bg-white shadow-sm sm:w-72">
                      <div className="border-b border-slate-100 px-3 py-2.5">
                        <Typography.Text className="text-fluid-lg text-slate-700">
                          设备列表
                        </Typography.Text>
                        <Typography.Text className="ml-1 text-fluid-sm text-slate-400">
                          {devices.length}
                        </Typography.Text>
                      </div>
                      <div className="flex-1 overflow-y-auto">
                        {devices.map((record) => {
                          const isSelected = selectedDevice?.deviceCode === record.deviceCode;
                          const diag = resolveDeviceRuntimeDiagnostic(record);
                          return (
                            <div
                              key={record.deviceCode}
                              className={`flex cursor-pointer items-center gap-2.5 border-b border-slate-50 px-3 py-2.5 transition last:border-0 ${
                                isSelected ? 'bg-brand-50' : 'hover:bg-slate-50'
                              }`}
                              onClick={() => setSelectedDeviceCode(record.deviceCode)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => { if (e.key === 'Enter') setSelectedDeviceCode(record.deviceCode); }}
                            >
                              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${record.status === 'online' ? 'bg-brand-500' : 'bg-slate-300'}`} />
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-fluid-base font-medium text-slate-800">
                                  {record.name || record.deviceCode}
                                </div>
                                <div className="truncate text-fluid-xs text-slate-400 font-mono">{record.deviceCode}</div>
                              </div>
                              <Tag className="shrink-0 text-fluid-xs py-0" color={diag.color} bordered={false}>
                                {diag.label}
                              </Tag>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Right panel */}
                    <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/70 bg-white shadow-sm">
                      {selectedDevice ? (
                        <div className="flex flex-1 flex-col overflow-y-auto">
                          {/* Header */}
                          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                            <div>
                              <Typography.Title level={5} className="mb-0.5 text-fluid-lg">
                                {selectedDevice.name || selectedDevice.deviceCode}
                              </Typography.Title>
                              <Typography.Text className="font-mono text-fluid-base text-slate-400" copyable>
                                {selectedDevice.deviceCode}
                              </Typography.Text>
                            </div>
                            <div className="flex items-center gap-2">
                              <Tag color={statusMap[selectedDevice.status].color}>{statusMap[selectedDevice.status].text}</Tag>
                              <Tag color={selectedDevice.isEnabled ? 'success' : 'error'}>{selectedDevice.isEnabled ? '已授权' : '已停用'}</Tag>
                              {canUpdateDevice && (
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-fluid-base text-slate-600 transition hover:bg-slate-50 hover:text-brand-700"
                                  onClick={() => openDeviceEdit(selectedDevice)}
                                >
                                  <IconEdit size={15} />
                                  编辑
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Detail grid */}
                          <div className="grid grid-cols-2 gap-4 p-5">
                            {(() => {
                              const sd = resolveDeviceRuntimeDiagnostic(selectedDevice);
                              return (
                                <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <Typography.Text className="text-fluid-lg text-slate-700">运行诊断</Typography.Text>
                                    <Tag className="shrink-0 text-fluid-xs" color={sd.color} bordered={false}>{sd.label}</Tag>
                                  </div>
                                  <div className="mt-2 flex items-center gap-2">
                                    <span className={`inline-block h-3 w-3 rounded-full ${sd.level === 'ready' ? 'bg-brand-500' : 'bg-amber-400'}`} />
                                    <span className="text-fluid-base text-slate-600">{sd.hint}</span>
                                  </div>
                                </div>
                              );
                            })()}

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <Typography.Text className="text-fluid-lg text-slate-700">软件到期时间</Typography.Text>
                              <div className="mt-2 text-fluid-base text-slate-600">
                                {selectedDeviceExpiration?.softwareExpiration ?? '-'}
                              </div>
                            </div>

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <Typography.Text className="text-fluid-lg text-slate-700">大模型到期时间</Typography.Text>
                              <div className="mt-2 text-fluid-base text-slate-600">
                                {selectedDeviceExpiration?.modelExpiration ?? '-'}
                              </div>
                            </div>

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <div className="flex items-center justify-between gap-2">
                                <Typography.Text className="text-fluid-lg text-slate-700">资源绑定</Typography.Text>
                                <Tag className="shrink-0 text-fluid-xs" color="default" bordered={false}>{selectedDevice.applicationName || '未绑定资源'}</Tag>
                              </div>
                              <div className="mt-2 flex items-center gap-1 text-fluid-base">
                                <span className={`rounded-md px-1.5 py-0.5 ${selectedDevice.agentApplicationName ? 'bg-purple-50 text-purple-700' : 'bg-amber-50 text-amber-700'}`}>
                                  {selectedDevice.agentApplicationName || '待绑定智能体'}
                                </span>
                              </div>
                            </div>

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <div className="flex items-center justify-between gap-2">
                                <Typography.Text className="text-fluid-lg text-slate-700">音色</Typography.Text>
                                <Tag className="shrink-0 text-fluid-xs" color="default" bordered={false}>{selectedDevice.voiceToneName || '未绑定'}</Tag>
                              </div>
                              <div className="mt-2 text-fluid-base text-slate-600 font-mono">{selectedDevice.voiceToneCode || '-'}</div>
                            </div>

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <div className="flex items-center justify-between gap-2">
                                <Typography.Text className="text-fluid-lg text-slate-700">系统信息</Typography.Text>
                                <Tag className="shrink-0 text-fluid-xs" color="default" bordered={false}>{selectedDevice.softwareVersion || '-'}</Tag>
                              </div>
                              <div className="mt-2 text-fluid-base text-slate-600 break-all">{selectedDevice.systemVersion || '-'}</div>
                            </div>

                            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 xl:col-span-1">
                              <div className="flex items-center justify-between gap-2">
                                <Typography.Text className="text-fluid-lg text-slate-700">心跳</Typography.Text>
                                <Tag className="shrink-0 text-fluid-xs" color="default" bordered={false}>{selectedDevice.lastHeartbeat || '-'}</Tag>
                              </div>
                              <div className="mt-2 text-fluid-base text-slate-600">{selectedDevice.registeredAt ? `注册于 ${selectedDevice.registeredAt.slice(0, 10)}` : '-'}</div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-1 items-center justify-center">
                          <Empty description="选择一个设备查看详情" />
                        </div>
                      )}
                    </div>
                  </div>
                )}
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
              <Space direction="vertical" size={16} className="w-full">
                <div className="flex items-center justify-between">
                  <Typography.Text className="text-fluid-base text-slate-500">
                    共 {applications.length} 个应用
                  </Typography.Text>
                  {canCreateDevice ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-4 py-1.5 text-fluid-sm font-medium text-white transition hover:bg-brand-800"
                      onClick={openApplicationCreate}
                    >
                      <IconPlus size={16} />
                      新建应用
                    </button>
                  ) : null}
                </div>
                {applications.length === 0 ? (
                  <Empty description="暂无应用" />
                ) : (
                  <Table
                    dataSource={applications}
                    columns={applicationColumns}
                    rowKey="id"
                    size="small"
                    pagination={false}
                    showHeader
                    rowClassName={(record) =>
                      `cursor-pointer transition ${selectedApplicationId === record.id ? 'bg-brand-50/60' : ''}`
                    }
                    onRow={(record) => ({
                      onClick: () => setSelectedApplicationId(record.id),
                    })}
                    scroll={{ x: 760 }}
                  />
                )}
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
      </div>
      </div>

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
          <Form.Item noStyle shouldUpdate={(prev, next) => prev.voiceToneId !== next.voiceToneId}>
            {({ getFieldValue }) => {
              const voiceToneSelected = Boolean(getFieldValue('voiceToneId'));
              return (
                <div className="grid gap-x-6 md:grid-cols-2">
                  <Form.Item
                    label="语速"
                    name={['voiceToneConfig', 'speechRate']}
                    rules={[{ required: voiceToneSelected, message: '请设置语速' }]}
                  >
                    <Slider min={0.5} max={2} step={0.05} disabled={!voiceToneSelected} />
                  </Form.Item>
                  <Form.Item
                    label="语调"
                    name={['voiceToneConfig', 'pitchRate']}
                    rules={[{ required: voiceToneSelected, message: '请设置语调' }]}
                  >
                    <Slider min={0.5} max={2} step={0.05} disabled={!voiceToneSelected} />
                  </Form.Item>
                  <Form.Item
                    label="音量大小"
                    name={['voiceToneConfig', 'volume']}
                    rules={[{ required: voiceToneSelected, message: '请设置音量大小' }]}
                  >
                    <Slider min={0} max={100} step={1} disabled={!voiceToneSelected} />
                  </Form.Item>
                </div>
              );
            }}
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
