import { Button, Space, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { IconLink } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import type { DeviceActivationLogRecord, DeviceAuthorizationRequestRecord } from '../../api/modules/devices';
import { bindingStatusMap, logActionMap, runtimeStatusMap } from './constants';
import { getInfoText } from './utils';

type DeviceAuthorizationColumnsOptions = {
  renderEditableDeviceName: (record: DeviceAuthorizationRequestRecord) => ReactNode;
  openBind: (record: DeviceAuthorizationRequestRecord, mode?: 'bind' | 'authorize') => void;
  handleIgnore: (record: DeviceAuthorizationRequestRecord) => void;
  handleRevoke: (record: DeviceAuthorizationRequestRecord) => void;
};

export const useDeviceAuthorizationColumns = ({
  renderEditableDeviceName,
  openBind,
  handleIgnore,
  handleRevoke,
}: DeviceAuthorizationColumnsOptions) => {
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
        <Button size="small" type="primary" icon={<IconLink />} onClick={() => openBind(record)}>
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
  return { requestColumns, authorizationColumns, logColumns };
};
