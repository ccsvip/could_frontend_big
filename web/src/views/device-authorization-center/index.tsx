import {
  Form,
  Modal,
  Space,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  bindDeviceAuthorizationRequest,
  authorizeDevice,
  fetchDeviceActivationLogs,
  fetchDeviceAuthorizations,
  fetchDeviceAuthorizationRequests,
  ignoreDeviceAuthorizationRequest,
  revokeDeviceAuthorization,
  updateDeviceAuthorizationRequestName,
  type DeviceActivationLogRecord,
  type DeviceAuthorizationRequestRecord,
} from '../../api/modules/devices';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import { EditableDeviceNameCell } from './components/EditableDeviceNameCell';
import { DeviceAuthorizationModal } from './components/DeviceAuthorizationModal';
import { DeviceAuthorizationTabs } from './components/DeviceAuthorizationTabs';
import { DeviceAuthorizationToolbar } from './components/DeviceAuthorizationToolbar';
import { useDeviceAuthorizationColumns } from './columns';
import type { BindForm, BindMode } from './types';
import {
  buildBindPayload,
  buildTenantOptions,
} from './utils';

export const DeviceAuthorizationCenterPage = () => {
  const [requests, setRequests] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [authorizations, setAuthorizations] = useState<DeviceAuthorizationRequestRecord[]>([]);
  const [logs, setLogs] = useState<DeviceActivationLogRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
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

  const tenantOptions = useMemo(() => buildTenantOptions(tenants), [tenants]);

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
      authorizationType: record.authorizationType,
      expiresAt: record.expiresAt ? dayjs(record.expiresAt) : null,
      isEnabled: record.isEnabled,
    });
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

  const renderEditableDeviceName = (record: DeviceAuthorizationRequestRecord) => (
    <EditableDeviceNameCell
      record={record}
      editingDeviceCode={editingDeviceCode}
      editingDeviceName={editingDeviceName}
      saving={nameSaving}
      onOpenEdit={openNameEdit}
      onNameChange={setEditingDeviceName}
      onSave={(target) => void handleNameSave(target)}
      onCancel={cancelNameEdit}
    />
  );


  const { requestColumns, authorizationColumns, logColumns } = useDeviceAuthorizationColumns({
    renderEditableDeviceName,
    openBind,
    handleIgnore,
    handleRevoke,
  });

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

      <DeviceAuthorizationTabs
        requestColumns={requestColumns}
        authorizationColumns={authorizationColumns}
        logColumns={logColumns}
        requests={requests}
        authorizations={authorizations}
        logs={logs}
        requestLoading={requestLoading}
        authorizationLoading={authorizationLoading}
        logLoading={logLoading}
        requestPage={requestPage}
        authorizationPage={authorizationPage}
        logPage={logPage}
        requestTotal={requestTotal}
        authorizationTotal={authorizationTotal}
        logTotal={logTotal}
        onRequestPageChange={setRequestPage}
        onAuthorizationPageChange={setAuthorizationPage}
        onLogPageChange={setLogPage}
      />

      <DeviceAuthorizationModal
        request={bindingRequest}
        mode={bindMode}
        form={bindForm}
        tenantOptions={tenantOptions}
        saving={bindSaving}
        onCancel={() => setBindingRequest(null)}
        onSave={handleModalSave}
      />
    </Space>
  );
};
