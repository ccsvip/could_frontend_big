import { IconReload, IconSearch } from '@tabler/icons-react';
import { Button, Input, Select, Typography } from 'antd';
import type { TenantRecord } from '../../../api/modules/tenants';
import type { DeviceAuthorizationRequestRecord } from '../../../api/modules/devices';

type DeviceAuthorizationToolbarProps = {
  bindingStatus: DeviceAuthorizationRequestRecord['bindingStatus'] | 'all';
  tenantFilter?: number;
  keyword: string;
  tenants: TenantRecord[];
  onBindingStatusChange: (value: DeviceAuthorizationRequestRecord['bindingStatus'] | 'all') => void;
  onTenantFilterChange: (value?: number) => void;
  onKeywordChange: (value: string) => void;
  onSearch: () => void;
};

export const DeviceAuthorizationToolbar = ({
  bindingStatus,
  tenantFilter,
  keyword,
  tenants,
  onBindingStatusChange,
  onTenantFilterChange,
  onKeywordChange,
  onSearch,
}: DeviceAuthorizationToolbarProps) => {
  const tenantOptions = tenants.map((item) => ({ label: item.name, value: item.id }));

  return (
    <div className="page-hero">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-700">
            <span className="inline-block h-1 w-1 rounded-full bg-brand-600" />
            Device Authorization
          </div>
          <Typography.Title level={4} className="mb-1 font-semibold text-slate-900">
            设备授权中心
          </Typography.Title>
          <Typography.Text className="text-[13px] text-slate-500">
            处理安卓上报的设备请求，将设备归属到公司，并追踪授权请求日志。
          </Typography.Text>
        </div>
        <div className="grid gap-2 md:grid-cols-[180px_180px_minmax(200px,1fr)_auto]">
          <Select
            value={bindingStatus}
            onChange={onBindingStatusChange}
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
            onChange={onTenantFilterChange}
            options={tenantOptions}
          />
          <Input
            value={keyword}
            prefix={<IconSearch />}
            placeholder="搜索设备码或设备名称"
            onChange={(event) => onKeywordChange(event.target.value)}
            onPressEnter={onSearch}
          />
          <Button icon={<IconReload />} onClick={onSearch}>
            刷新
          </Button>
        </div>
      </div>
    </div>
  );
};
