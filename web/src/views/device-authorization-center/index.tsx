import {
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  FileSearchOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import {
  Button,
  Form,
  Input,
  Modal,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  bindDeviceAuthorizationRequest,
  authorizeDevice,
  fetchDeviceActivationLogs,
  fetchDeviceApplications,
  fetchDeviceAuthorizations,
  fetchDeviceAuthorizationRequests,
  fetchDeviceGroups,
  ignoreDeviceAuthorizationRequest,
  revokeDeviceAuthorization,
  updateDeviceAuthorizationRequestName,
  type DeviceActivationLogRecord,
  type DeviceApplicationRecord,
  type DeviceAuthorizationRequestRecord,
  type DeviceGroupRecord,
} from '../../api/modules/devices';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import { fetchAgentApplications, type AgentApplicationRecord } from '../../api/modules/applications';
import { AuthorizationTableCard } from './components/AuthorizationTableCard';
import { DeviceAuthorizationModal } from './components/DeviceAuthorizationModal';
import { DeviceAuthorizationToolbar } from './components/DeviceAuthorizationToolbar';
import { bindingStatusMap, logActionMap, runtimeStatusMap } from './constants';
import type { BindForm, BindMode } from './types';
import { buildBindPayload, getInfoText } from './utils';

export const DeviceAuthorizationCenterPage = () => {
  const [requests, setRequests] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [authorizations, setAuthorizations] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [logs, setLogs] = useState<DeviceActivationLogRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
  const [agentApplications, setAgentApplications] = useState<AgentApplicationRecord[]>([]);
  const [groups, setGroups] = useState<DeviceGroupRecord[]>([]);
  const [requestTotal, setRequestTotal] = useState(0);
  const [authorizationTotal, setAuthorizationTotal] = useState(0);
  const [logTotal, setLogTotal] = useState(0);
  const [requestPage, setRequestPage] = useState(1);
  const [authorizationPage, setAuthorizationPage] = useState(1);
  const [logPage, setLogPage] = useState(1);
  const [requestLoading, setRequestLoading] = useState(true);
  const [authorizationLoading, setAuthorizationLoading] = useState(true);
  const [logLoading, setLogLoading] = useState(true);
  const [bindingStatus, setBindingStatus] = useState<'pending' | 'bound' | 'ignored' | 'all'>('pending');
  const [keyword, setKeyword] = useState('');
  const [tenantFilter, setTenantFilter] = useState<number | undefined>(undefined);
  const [bindingRequest, setBindingRequest] = useState<DeviceAuthorizationRequestRecord | null>(null);
  const [bindMode, setBindMode] = useState<BindMode>('bind');
  const [bindSaving, setBindSaving] = useState(false);
  const [editingDeviceCode, setEditingDeviceCode] = useState<string | null>(null);
  const [editingDeviceName, setEditingDeviceName] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [bindForm] = Form.useForm<BindForm>();
  const hasLoadedRef = useRef(false);

  const tenantOptions = useMemo(() => tenants.map((item) => ({ label: item.name, value: item.id })), [tenants]);
  const applicationOptions = useMemo(
    () => [
      { label: '暂不绑定资源应用', value: null as number | null },
      ...applications.map((item) => ({ label: item.name, value: item.id })),
    ],
    [applications],
  );
  const agentApplicationOptions = useMemo(
    () => [
      { label: '请选择智能体', value: null as number | null },
      ...agentApplications.map((item) => ({ label: item.name, value: item.id })),
    ],
    [agentApplications],
  );
  const groupOptions = useMemo(
    () => [{ label: '暂不分组', value: null as number | null }, ...groups.map((item) => ({ label: item.name, value: item.id }))],
    [groups],
  );

  const loadRequests = async (page = requestPage) => {
    setRequestLoading(true);
    try {
      const data = await fetchDeviceAuthorizationRequests({
        page,
        bindingStatus,
        keyword,
        tenantId: tenantFilter,
      });
      setRequests(data.results);
      setRequestTotal(data.count);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setRequestLoading(false);
    }
  };

  const loadLogs = async (page = logPage) => {
    setLogLoading(true);
    try {
      const data = await fetchDeviceActivationLogs({
        page,
        keyword,
        tenantId: tenantFilter,
      });
      setLogs(data.results);
      setLogTotal(data.count);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setLogLoading(false);
    }
  };

  const loadAuthorizations = async (page = authorizationPage) => {
    setAuthorizationLoading(true);
    try {
      const data = await fetchDeviceAuthorizations({
        page,
        keyword,
        tenantId: tenantFilter,
      });
      setAuthorizations(data.results);
      setAuthorizationTotal(data.count);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setAuthorizationLoading(false);
    }
  };

  const loadTenantOwnedOptions = async (tenantId: number) => {
    try {
      const [applicationResponse, agentApplicationResponse, groupResponse] = await Promise.all([
        fetchDeviceApplications({ tenant: tenantId }),
        fetchAgentApplications({ page: 1, tenant: tenantId }),
        fetchDeviceGroups({ tenant: tenantId }),
      ]);
      setApplications(applicationResponse.results);
      setAgentApplications(agentApplicationResponse.results.filter((item) => item.isActive));
      setGroups(groupResponse.results);
    } catch {
      setApplications([]);
      setAgentApplications([]);
      setGroups([]);
    }
  };

  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;
    void (async () => {
      try {
        const tenantResponse = await fetchTenants({ page_size: 100 });
        setTenants(tenantResponse.results);
      } catch {
        // Global interceptor displays request errors.
      }
      void loadRequests(1);
      void loadAuthorizations(1);
      void loadLogs(1);
    })();
  }, []);

  useEffect(() => {
    void loadRequests(requestPage);
  }, [requestPage, bindingStatus, tenantFilter]);

  useEffect(() => {
    void loadLogs(logPage);
  }, [logPage, tenantFilter]);

  useEffect(() => {
    void loadAuthorizations(authorizationPage);
  }, [authorizationPage, tenantFilter]);

  const handleSearch = () => {
    setRequestPage(1);
    setAuthorizationPage(1);
    setLogPage(1);
    void loadRequests(1);
    void loadAuthorizations(1);
    void loadLogs(1);
  };

  const openBind = (record: DeviceAuthorizationRequestRecord, mode: 'bind' | 'authorize' = 'bind') => {
    setBindingRequest(record);
    setBindMode(mode);
    const tenantId = record.tenantId ?? tenants[0]?.id;
    bindForm.setFieldsValue({
      tenantId,
      applicationId: record.applicationId ?? null,
      agentApplicationId: record.agentApplicationId ?? null,
      groupId: record.groupId ?? null,
      authorizationType: record.authorizationType,
      expiresAt: record.expiresAt ? dayjs(record.expiresAt) : null,
      isEnabled: record.isEnabled,
    });
    if (tenantId) {
      void loadTenantOwnedOptions(tenantId);
    }
  };

  const handleTenantChange = (tenantId: number) => {
    bindForm.setFieldsValue({ applicationId: null, agentApplicationId: null, groupId: null });
    void loadTenantOwnedOptions(tenantId);
  };

  const saveAuthorizationChange = async (mode: BindMode) => {
    if (!bindingRequest) return;
    const values = await bindForm.validateFields();
    setBindSaving(true);
    try {
      const saveRequest = mode === 'bind' ? bindDeviceAuthorizationRequest : authorizeDevice;
      await saveRequest(bindingRequest.deviceCode, buildBindPayload(values));
      message.success(mode === 'bind' ? '设备已绑定到公司' : '设备已再次授权');
      setBindingRequest(null);
      void loadRequests(requestPage);
      void loadAuthorizations(authorizationPage);
      void loadLogs(logPage);
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setBindSaving(false);
    }
  };

  const handleModalSave = () => {
    void saveAuthorizationChange(bindMode);
  };

  const handleIgnore = (record: DeviceAuthorizationRequestRecord) => {
    Modal.confirm({
      title: '忽略设备请求',
      content: `忽略后待处理列表将隐藏 ${record.deviceCode}，设备再次上报会重新出现。`,
      okText: '忽略',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await ignoreDeviceAuthorizationRequest(record.deviceCode);
        message.success('设备请求已忽略');
        void loadRequests(requestPage);
        void loadLogs(logPage);
      },
    });
  };

  const handleRevoke = (record: DeviceAuthorizationRequestRecord) => {
    Modal.confirm({
      title: '撤销设备授权',
      content: `撤销后 ${record.deviceCode} 将被停用，安卓端无法继续拉取配置。`,
      okText: '撤销授权',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await revokeDeviceAuthorization(record.deviceCode);
        message.success('设备授权已撤销');
        void loadAuthorizations(authorizationPage);
        void loadLogs(logPage);
      },
    });
  };

  const openNameEdit = (record: DeviceAuthorizationRequestRecord) => {
    setEditingDeviceCode(record.deviceCode);
    setEditingDeviceName(record.name);
  };

  const cancelNameEdit = () => {
    setEditingDeviceCode(null);
    setEditingDeviceName('');
  };

  const applyRenamedDevice = (updated: DeviceAuthorizationRequestRecord) => {
    const updateRecord = (item: DeviceAuthorizationRequestRecord) =>
      item.deviceCode === updated.deviceCode ? { ...item, name: updated.name, updated_at: updated.updated_at } : item;
    setRequests((items) => items.map(updateRecord));
    setAuthorizations((items) => items.map(updateRecord));
    setLogs((items) =>
      items.map((item) => (item.code === updated.deviceCode ? { ...item, deviceName: updated.name } : item)),
    );
  };

  const handleNameSave = async (record: DeviceAuthorizationRequestRecord) => {
    const nextName = editingDeviceName.trim();
    if (!nextName) {
      message.warning('请输入设备名称');
      return;
    }
    setNameSaving(true);
    try {
      const updated = await updateDeviceAuthorizationRequestName(record.deviceCode, nextName);
      applyRenamedDevice(updated);
      cancelNameEdit();
      message.success('设备名称已保存');
    } catch {
      // Global interceptor displays request errors.
    } finally {
      setNameSaving(false);
    }
  };

  const renderEditableDeviceName = (record: DeviceAuthorizationRequestRecord) => {
    if (editingDeviceCode !== record.deviceCode) {
      return (
        <Typography.Text className="cursor-text" onDoubleClick={() => openNameEdit(record)}>
          {record.name || '-'}
        </Typography.Text>
      );
    }
    return (
      <Space.Compact className="w-full">
        <Input
          autoFocus
          size="small"
          value={editingDeviceName}
          onChange={(event) => setEditingDeviceName(event.target.value)}
          onPressEnter={() => void handleNameSave(record)}
        />
        <Button
          size="small"
          type="primary"
          icon={<CheckOutlined />}
          loading={nameSaving}
          onClick={() => void handleNameSave(record)}
        />
        <Button size="small" icon={<CloseOutlined />} disabled={nameSaving} onClick={cancelNameEdit} />
      </Space.Compact>
    );
  };

  const requestColumns: ColumnsType<DeviceAuthorizationRequestRecord> = [
    {
      title: '设备码',
      dataIndex: 'deviceCode',
      key: 'deviceCode',
      fixed: 'left',
      width: 210,
      render: (value: string) => (
        <Typography.Text className="!text-xs" copyable>
          {value}
        </Typography.Text>
      ),
    },
    { title: '设备名称（双击可修改）', dataIndex: 'name', key: 'name', width: 220, render: (_, record) => renderEditableDeviceName(record) },
    {
      title: '所属公司',
      dataIndex: 'tenantName',
      key: 'tenantName',
      width: 160,
      render: (value: string) => value || <span className="text-slate-400">未绑定</span>,
    },
    {
      title: '绑定状态',
      key: 'bindingStatus',
      width: 130,
      render: (_, record) => {
        const binding = bindingStatusMap[record.bindingStatus];
        const runtime = runtimeStatusMap[record.runtimeStatus];
        return (
          <Space size={4} wrap>
            <Tag color={binding.color}>{binding.text}</Tag>
            {record.bindingStatus === 'bound' ? <Tag color={runtime.color}>{runtime.text}</Tag> : null}
          </Space>
        );
      },
    },
    {
      title: '智能体',
      dataIndex: 'agentApplicationName',
      key: 'agentApplicationName',
      width: 160,
      render: (value: string) => value || '-',
    },
    {
      title: '资源应用',
      dataIndex: 'applicationName',
      key: 'applicationName',
      width: 160,
      render: (value: string) => value || '-',
    },
    {
      title: '版本 / 主板',
      key: 'deviceInfo',
      width: 190,
      render: (_, record) => {
        const info = record.latestActivationDeviceInfo;
        return (
          <Space direction="vertical" size={0}>
            <span>{getInfoText(info, 'softwareVersion') || record.softwareVersion || '-'}</span>
            <Typography.Text type="secondary" className="!text-xs">
              {getInfoText(info, 'mainboardInfo') || record.mainboardInfo || '-'}
            </Typography.Text>
          </Space>
        );
      },
    },
    { title: '最近请求', dataIndex: 'latestActivationAt', key: 'latestActivationAt', width: 180, render: (value) => value || '-' },
    { title: '请求 IP', dataIndex: 'latestActivationIp', key: 'latestActivationIp', width: 130, render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 160,
      render: (_, record) => (
        <Space size={6}>
          <Button size="small" type="primary" icon={<LinkOutlined />} onClick={() => openBind(record)}>
            绑定
          </Button>
          <Button size="small" danger onClick={() => handleIgnore(record)}>
            忽略
          </Button>
        </Space>
      ),
    },
  ];

  const authorizationColumns: ColumnsType<DeviceAuthorizationRequestRecord> = [
    {
      title: '设备码',
      dataIndex: 'deviceCode',
      key: 'deviceCode',
      fixed: 'left',
      width: 210,
      render: (value: string) => (
        <Typography.Text className="!text-xs" copyable>
          {value}
        </Typography.Text>
      ),
    },
    { title: '设备名称', dataIndex: 'name', key: 'name', width: 220, render: (_, record) => renderEditableDeviceName(record) },
    { title: '所属公司', dataIndex: 'tenantName', key: 'tenantName', width: 160 },
    { title: '智能体', dataIndex: 'agentApplicationName', key: 'agentApplicationName', width: 160, render: (value) => value || '-' },
    { title: '资源应用', dataIndex: 'applicationName', key: 'applicationName', width: 160, render: (value) => value || '-' },
    {
      title: '授权',
      key: 'authorization',
      width: 150,
      render: (_, record) => (
        <Space size={4} wrap>
          <Tag color={record.authorizationType === 'permanent' ? 'geekblue' : 'gold'}>
            {record.authorizationTypeLabel}
          </Tag>
          <Tag color={record.isEnabled ? 'success' : 'error'}>{record.isEnabled ? '启用' : '停用'}</Tag>
        </Space>
      ),
    },
    {
      title: '到期时间',
      dataIndex: 'expiresAt',
      key: 'expiresAt',
      width: 180,
      render: (value: string | null, record) => (record.authorizationType === 'permanent' ? '永久' : value || '-'),
    },
    { title: '最近心跳', dataIndex: 'lastHeartbeat', key: 'lastHeartbeat', width: 180, render: (value) => value || '-' },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 170,
      render: (_, record) => (
        <Space size={6}>
          <Button size="small" type="primary" onClick={() => openBind(record, 'authorize')}>
            再次授权
          </Button>
          <Button size="small" danger onClick={() => handleRevoke(record)}>
            撤销
          </Button>
        </Space>
      ),
    },
  ];

  const logColumns: ColumnsType<DeviceActivationLogRecord> = [
    { title: '请求时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
    {
      title: '设备码',
      dataIndex: 'code',
      key: 'code',
      width: 210,
      render: (value: string) => (
        <Typography.Text className="!text-xs" copyable>
          {value}
        </Typography.Text>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 110,
      render: (action: DeviceActivationLogRecord['action']) => {
        const meta = logActionMap[action];
        return <Tag color={meta.color}>{meta.text}</Tag>;
      },
    },
    { title: '设备名称', dataIndex: 'deviceName', key: 'deviceName', width: 160, render: (value) => value || '-' },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      width: 90,
      render: (value: boolean) => <Tag color={value ? 'success' : 'error'}>{value ? '成功' : '失败'}</Tag>,
    },
    { title: '消息', dataIndex: 'message', key: 'message', width: 220, ellipsis: true },
    { title: '所属公司', dataIndex: 'tenantName', key: 'tenantName', width: 150, render: (value) => value || '-' },
    { title: '智能体', dataIndex: 'agentApplicationName', key: 'agentApplicationName', width: 150, render: (value) => value || '-' },
    { title: '资源应用', dataIndex: 'applicationName', key: 'applicationName', width: 150, render: (value) => value || '-' },
    {
      title: '版本 / 系统',
      key: 'version',
      width: 180,
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <span>{getInfoText(record.deviceInfo, 'softwareVersion') || '-'}</span>
          <Typography.Text type="secondary" className="!text-xs">
            {getInfoText(record.deviceInfo, 'systemVersion') || '-'}
          </Typography.Text>
        </Space>
      ),
    },
    { title: 'IP', dataIndex: 'ipAddress', key: 'ipAddress', width: 130, render: (value) => value || '-' },
  ];

  return (
    <Space direction="vertical" size={16} className="w-full">
      <DeviceAuthorizationToolbar
        bindingStatus={bindingStatus}
        tenantFilter={tenantFilter}
        keyword={keyword}
        tenants={tenants}
        onBindingStatusChange={(value) => {
          setBindingStatus(value);
          setRequestPage(1);
        }}
        onTenantFilterChange={(value) => {
          setTenantFilter(value);
          setRequestPage(1);
          setAuthorizationPage(1);
          setLogPage(1);
        }}
        onKeywordChange={setKeyword}
        onSearch={handleSearch}
      />

      <Tabs
        items={[
          {
            key: 'requests',
            label: (
              <Space size={6}>
                <CheckCircleOutlined />
                设备请求
              </Space>
            ),
            children: (
              <AuthorizationTableCard
                columns={requestColumns}
                dataSource={requests}
                rowKey="deviceCode"
                loading={requestLoading}
                scrollX={1480}
                currentPage={requestPage}
                total={requestTotal}
                emptyText="暂无设备请求"
                onPageChange={setRequestPage}
              />
            ),
          },
          {
            key: 'authorizations',
            label: (
              <Space size={6}>
                <LinkOutlined />
                授权管理
              </Space>
            ),
            children: (
              <AuthorizationTableCard
                columns={authorizationColumns}
                dataSource={authorizations}
                rowKey="deviceCode"
                loading={authorizationLoading}
                scrollX={1380}
                currentPage={authorizationPage}
                total={authorizationTotal}
                emptyText="暂无授权设备"
                onPageChange={setAuthorizationPage}
              />
            ),
          },
          {
            key: 'logs',
            label: (
              <Space size={6}>
                <FileSearchOutlined />
                授权日志
              </Space>
            ),
            children: (
              <AuthorizationTableCard
                columns={logColumns}
                dataSource={logs}
                rowKey="id"
                loading={logLoading}
                scrollX={1390}
                currentPage={logPage}
                total={logTotal}
                emptyText="暂无授权日志"
                onPageChange={setLogPage}
              />
            ),
          },
        ]}
      />

      <DeviceAuthorizationModal
        request={bindingRequest}
        mode={bindMode}
        form={bindForm}
        tenantOptions={tenantOptions}
        applicationOptions={applicationOptions}
        agentApplicationOptions={agentApplicationOptions}
        groupOptions={groupOptions}
        saving={bindSaving}
        onCancel={() => setBindingRequest(null)}
        onSave={handleModalSave}
        onTenantChange={handleTenantChange}
      />
    </Space>
  );
};
