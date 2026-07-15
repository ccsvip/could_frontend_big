import {
  IconCircleCheck,
  IconFileSearch,
  IconLink,
} from '@tabler/icons-react';
import { Space, Tabs } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type {
  DeviceActivationLogRecord,
  DeviceAuthorizationRequestRecord,
} from '../../../api/modules/devices';
import { AuthorizationTableCard } from './AuthorizationTableCard';

type DeviceAuthorizationTabsProps = {
  requestColumns: ColumnsType<DeviceAuthorizationRequestRecord>;
  authorizationColumns: ColumnsType<DeviceAuthorizationRequestRecord>;
  logColumns: ColumnsType<DeviceActivationLogRecord>;
  requests: DeviceAuthorizationRequestRecord[];
  authorizations: DeviceAuthorizationRequestRecord[];
  logs: DeviceActivationLogRecord[];
  requestLoading: boolean;
  authorizationLoading: boolean;
  logLoading: boolean;
  requestPage: number;
  authorizationPage: number;
  logPage: number;
  requestTotal: number;
  authorizationTotal: number;
  logTotal: number;
  onRequestPageChange: (page: number) => void;
  onAuthorizationPageChange: (page: number) => void;
  onLogPageChange: (page: number) => void;
};

export const DeviceAuthorizationTabs = ({
  requestColumns,
  authorizationColumns,
  logColumns,
  requests,
  authorizations,
  logs,
  requestLoading,
  authorizationLoading,
  logLoading,
  requestPage,
  authorizationPage,
  logPage,
  requestTotal,
  authorizationTotal,
  logTotal,
  onRequestPageChange,
  onAuthorizationPageChange,
  onLogPageChange,
}: DeviceAuthorizationTabsProps) => (
  <Tabs
    items={[
      {
        key: 'requests',
        label: (
          <Space size={6}>
            <IconCircleCheck />
            设备请求
          </Space>
        ),
        children: (
          <AuthorizationTableCard
            columns={requestColumns}
            dataSource={requests}
            rowKey={(record) => record.recordId}
            loading={requestLoading}
            scrollX={1480}
            currentPage={requestPage}
            total={requestTotal}
            emptyText="暂无设备请求"
            onPageChange={onRequestPageChange}
          />
        ),
      },
      {
        key: 'authorizations',
        label: (
          <Space size={6}>
            <IconLink />
            授权管理
          </Space>
        ),
        children: (
          <AuthorizationTableCard
            columns={authorizationColumns}
            dataSource={authorizations}
            rowKey={(record) => record.recordId}
            loading={authorizationLoading}
            scrollX={1500}
            currentPage={authorizationPage}
            total={authorizationTotal}
            emptyText="暂无授权设备"
            onPageChange={onAuthorizationPageChange}
          />
        ),
      },
      {
        key: 'logs',
        label: (
          <Space size={6}>
            <IconFileSearch />
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
            onPageChange={onLogPageChange}
          />
        ),
      },
    ]}
  />
);
