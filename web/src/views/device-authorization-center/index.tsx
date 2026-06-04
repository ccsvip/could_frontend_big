import {
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  FileSearchOutlined,
  LinkOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { type Dayjs } from 'dayjs';
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
  type DeviceAuthorizationType,
  type DeviceGroupRecord,
} from '../../api/modules/devices';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';

const PAGE_SIZE = 10;

type BindForm = {
  tenantId: number;
  applicationId?: number | null;
  groupId?: number | null;
  authorizationType: DeviceAuthorizationType;
  expiresAt?: Dayjs | null;
  isEnabled: boolean;
};

const getInfoText = (info: Record<string, unknown>, key: string) => {
  const value = info[key];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
};

const bindingStatusMap: Record<DeviceAuthorizationRequestRecord['bindingStatus'], { color: string; text: string }> = {
  pending: { color: 'warning', text: '待绑定公司' },
  bound: { color: 'success', text: '已绑定公司' },
  ignored: { color: 'default', text: '已忽略' },
};

const runtimeStatusMap: Record<DeviceAuthorizationRequestRecord['runtimeStatus'], { color: string; text: string }> = {
  waiting_application: { color: 'default', text: '待绑定应用' },
  ready: { color: 'processing', text: '可拉取资源' },
};

const logActionMap: Record<DeviceActivationLogRecord['action'], { color: string; text: string }> = {
  activate: { color: 'processing', text: '请求授权' },
  bind: { color: 'success', text: '绑定' },
  ignore: { color: 'default', text: '忽略' },
  authorize: { color: 'geekblue', text: '再次授权' },
  revoke: { color: 'error', text: '撤销授权' },
};

export const DeviceAuthorizationCenterPage = () => {
  const [requests, setRequests] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [authorizations, setAuthorizations] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [logs, setLogs] = useState<DeviceActivationLogRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [applications, setApplications] = useState<DeviceApplicationRecord[]>([]);
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
  const [bindMode, setBindMode] = useState<'bind' | 'authorize'>('bind');
  const [bindSaving, setBindSaving] = useState(false);
  const [editingDeviceCode, setEditingDeviceCode] = useState<string | null>(null);
  const [editingDeviceName, setEditingDeviceName] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [bindForm] = Form.useForm<BindForm>();
  const hasLoadedRef = useRef(false);

  const tenantOptions = useMemo(() => tenants.map((item) => ({ label: item.name, value: item.id })), [tenants]);
  const applicationOptions = useMemo(
    () => [{ label: '暂不绑定应用', value: null as number | null }, ...applications.map((item) => ({ label: item.name, value: item.id }))],
    [applications],
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
      const [applicationResponse, groupResponse] = await Promise.all([
        fetchDeviceApplications({ tenant: tenantId }),
        fetchDeviceGroups({ tenant: tenantId }),
      ]);
      setApplications(applicationResponse.results);
      setGroups(groupResponse.results);
    } catch {
      setApplications([]);
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
    bindForm.setFieldsValue({ applicationId: null, groupId: null });
    void loadTenantOwnedOptions(tenantId);
  };

  const handleBindSave = async () => {
    if (!bindingRequest) return;
    const values = await bindForm.validateFields();
    setBindSaving(true);
    try {
      await bindDeviceAuthorizationRequest(bindingRequest.deviceCode, {
        tenantId: values.tenantId,
        applicationId: values.applicationId ?? null,
        groupId: values.groupId ?? null,
        authorizationType: values.authorizationType,
        expiresAt: values.authorizationType === 'trial' ? values.expiresAt?.toISOString() : null,
        isEnabled: values.isEnabled,
      });
      message.success('设备已绑定到公司');
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

  const handleAuthorizeSave = async () => {
    if (!bindingRequest) return;
    const values = await bindForm.validateFields();
    setBindSaving(true);
    try {
      await authorizeDevice(bindingRequest.deviceCode, {
        tenantId: values.tenantId,
        applicationId: values.applicationId ?? null,
        groupId: values.groupId ?? null,
        authorizationType: values.authorizationType,
        expiresAt: values.authorizationType === 'trial' ? values.expiresAt?.toISOString() : null,
        isEnabled: values.isEnabled,
      });
      message.success('设备已再次授权');
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
    void (bindMode === 'bind' ? handleBindSave() : handleAuthorizeSave());
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
      title: '应用',
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
    { title: '应用', dataIndex: 'applicationName', key: 'applicationName', width: 160, render: (value) => value || '-' },
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
    { title: '应用', dataIndex: 'applicationName', key: 'applicationName', width: 150, render: (value) => value || '-' },
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
      <div className="page-hero">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-700">
              <span className="inline-block h-1 w-1 rounded-full bg-teal-600" />
              Device Authorization
            </div>
            <Typography.Title level={4} className="!mb-1 !font-semibold !text-slate-900">
              设备授权中心
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              处理安卓上报的设备请求，将设备归属到公司，并追踪授权请求日志。
            </Typography.Text>
          </div>
          <div className="grid gap-2 md:grid-cols-[180px_180px_minmax(200px,1fr)_auto]">
            <Select
              value={bindingStatus}
              onChange={(value) => {
                setBindingStatus(value);
                setRequestPage(1);
              }}
              options={[
                { label: '待绑定', value: 'pending' },
                { label: '已绑定', value: 'bound' },
                { label: '已忽略', value: 'ignored' },
                { label: '全部请求', value: 'all' },
              ]}
            />
            <Select
              allowClear
              placeholder="按公司筛选"
              value={tenantFilter}
              onChange={(value) => {
                setTenantFilter(value);
                setRequestPage(1);
                setAuthorizationPage(1);
                setLogPage(1);
              }}
              options={tenantOptions}
            />
            <Input
              value={keyword}
              prefix={<SearchOutlined />}
              placeholder="搜索设备码或设备名称"
              onChange={(event) => setKeyword(event.target.value)}
              onPressEnter={handleSearch}
            />
            <Button icon={<ReloadOutlined />} onClick={handleSearch}>
              刷新
            </Button>
          </div>
        </div>
      </div>

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
              <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
                <Table
                  columns={requestColumns}
                  dataSource={requests}
                  rowKey="deviceCode"
                  loading={requestLoading}
                  scroll={{ x: 1480 }}
                  pagination={{
                    current: requestPage,
                    pageSize: PAGE_SIZE,
                    total: requestTotal,
                    showSizeChanger: false,
                    onChange: (nextPage) => setRequestPage(nextPage),
                  }}
                  locale={{ emptyText: '暂无设备请求' }}
                />
              </Card>
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
              <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
                <Table
                  columns={authorizationColumns}
                  dataSource={authorizations}
                  rowKey="deviceCode"
                  loading={authorizationLoading}
                  scroll={{ x: 1380 }}
                  pagination={{
                    current: authorizationPage,
                    pageSize: PAGE_SIZE,
                    total: authorizationTotal,
                    showSizeChanger: false,
                    onChange: (nextPage) => setAuthorizationPage(nextPage),
                  }}
                  locale={{ emptyText: '暂无授权设备' }}
                />
              </Card>
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
              <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
                <Table
                  columns={logColumns}
                  dataSource={logs}
                  rowKey="id"
                  loading={logLoading}
                  scroll={{ x: 1390 }}
                  pagination={{
                    current: logPage,
                    pageSize: PAGE_SIZE,
                    total: logTotal,
                    showSizeChanger: false,
                    onChange: (nextPage) => setLogPage(nextPage),
                  }}
                  locale={{ emptyText: '暂无授权日志' }}
                />
              </Card>
            ),
          },
        ]}
      />

      <Modal
        title={
          bindingRequest
            ? `${bindMode === 'bind' ? '绑定设备' : '再次授权'} ${bindingRequest.deviceCode}`
            : bindMode === 'bind'
              ? '绑定设备'
              : '再次授权'
        }
        open={Boolean(bindingRequest)}
        onCancel={() => setBindingRequest(null)}
        onOk={handleModalSave}
        okText={bindMode === 'bind' ? '保存绑定' : '保存授权'}
        cancelText="取消"
        confirmLoading={bindSaving}
        destroyOnHidden
      >
        <Form<BindForm> form={bindForm} layout="vertical">
          <Form.Item label="所属公司" name="tenantId" rules={[{ required: true, message: '请选择公司' }]}>
            <Select options={tenantOptions} onChange={handleTenantChange} />
          </Form.Item>
          <Form.Item label="绑定应用" name="applicationId">
            <Select options={applicationOptions} optionFilterProp="label" showSearch />
          </Form.Item>
          <Form.Item label="设备分组" name="groupId">
            <Select options={groupOptions} optionFilterProp="label" showSearch />
          </Form.Item>
          <Form.Item label="授权类型" name="authorizationType" rules={[{ required: true, message: '请选择授权类型' }]}>
            <Select
              options={[
                { label: '永久', value: 'permanent' },
                { label: '试用', value: 'trial' },
              ]}
            />
          </Form.Item>
          <Form.Item dependencies={['authorizationType']} noStyle>
            {({ getFieldValue }) =>
              getFieldValue('authorizationType') === 'trial' ? (
                <Form.Item label="到期时间" name="expiresAt" rules={[{ required: true, message: '请选择到期时间' }]}>
                  <DatePicker
                    className="w-full"
                    format="YYYY-MM-DD HH:mm:ss"
                    placeholder="请选择到期时间"
                    showNow={false}
                    showTime={{ defaultValue: dayjs('23:59:59', 'HH:mm:ss') }}
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item label="启用设备" name="isEnabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
