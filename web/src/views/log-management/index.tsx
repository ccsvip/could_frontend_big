import { FileSearchOutlined } from '@ant-design/icons';
import { Card, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchOperationLogs,
  type OperationLogAction,
  type OperationLogRecord,
} from '../../api/modules/audit';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';

const PAGE_SIZE = 10;

const actionMap: Record<OperationLogAction, { color: string; text: string }> = {
  create: { color: 'success', text: '新增' },
  update: { color: 'processing', text: '修改' },
  delete: { color: 'error', text: '删除' },
};

const methodColorMap: Record<string, string> = {
  POST: 'green',
  PUT: 'gold',
  PATCH: 'gold',
  DELETE: 'red',
};

const statusColor = (code: number): string => {
  if (code >= 500) return 'error';
  if (code >= 400) return 'warning';
  if (code >= 200 && code < 300) return 'success';
  return 'default';
};

export const LogManagementPage = () => {
  const [logs, setLogs] = useState<OperationLogRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [tenantFilter, setTenantFilter] = useState<number | undefined>(undefined);
  const hasLoadedTenantsRef = useRef(false);

  const loadLogs = async (nextPage: number, tenant?: number) => {
    setLoading(true);
    try {
      const data = await fetchOperationLogs({ page: nextPage, tenant });
      setLogs(data.results);
      setTotal(data.count);
    } catch {
      // 错误已在拦截器中处理
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadLogs(page, tenantFilter);
  }, [page, tenantFilter]);

  useEffect(() => {
    if (hasLoadedTenantsRef.current) {
      return;
    }
    hasLoadedTenantsRef.current = true;
    void (async () => {
      try {
        const data = await fetchTenants({ page_size: 100 });
        setTenants(data.results);
      } catch {
        // 拦截器已提示
      }
    })();
  }, []);

  const columns: ColumnsType<OperationLogRecord> = useMemo(
    () => [
      {
        title: '操作人',
        dataIndex: 'actorUsername',
        key: 'actorUsername',
        width: 140,
        render: (value: string) => value || <span className="text-slate-400">匿名</span>,
      },
      {
        title: '所属公司',
        dataIndex: 'tenantName',
        key: 'tenantName',
        width: 160,
        render: (value: string | null) => value || <span className="text-slate-400">—</span>,
      },
      {
        title: '动作',
        dataIndex: 'action',
        key: 'action',
        width: 90,
        render: (action: OperationLogAction) => {
          const meta = actionMap[action];
          return <Tag color={meta?.color}>{meta?.text ?? action}</Tag>;
        },
      },
      {
        title: '请求方法',
        dataIndex: 'method',
        key: 'method',
        width: 110,
        render: (method: string) => <Tag color={methodColorMap[method] ?? 'default'}>{method}</Tag>,
      },
      {
        title: '请求路径',
        dataIndex: 'path',
        key: 'path',
        ellipsis: true,
        render: (path: string) => <span className="font-mono text-[13px] text-slate-700">{path}</span>,
      },
      {
        title: '状态码',
        dataIndex: 'statusCode',
        key: 'statusCode',
        width: 100,
        render: (code: number) => <Tag color={statusColor(code)}>{code}</Tag>,
      },
      {
        title: '操作时间',
        dataIndex: 'createdAt',
        key: 'createdAt',
        width: 180,
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" size={16} className="w-full">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-700">
              <span className="inline-block h-1 w-1 rounded-full bg-teal-600" />
              Operation Audit
            </div>
            <Typography.Title level={4} className="!mb-1 !text-slate-900 !font-semibold">
              操作日志审计
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              记录平台内各公司的写操作（新增 / 修改 / 删除），可按公司筛选追溯
            </Typography.Text>
          </div>
          <Select
            allowClear
            placeholder="按公司筛选"
            className="!w-full md:!w-60"
            value={tenantFilter}
            onChange={(value) => {
              setTenantFilter(value);
              setPage(1);
            }}
            options={tenants.map((tenant) => ({ value: tenant.id, label: tenant.name }))}
          />
        </div>
      </div>

      <Card
        variant="borderless"
        className="!rounded-xl !border !border-slate-200/70 !shadow-card"
        title={
          <Space size={8}>
            <FileSearchOutlined className="text-teal-700" />
            <span>操作日志列表</span>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          scroll={{ x: 880 }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            onChange: (nextPage) => setPage(nextPage),
          }}
          locale={{ emptyText: '暂无操作日志' }}
        />
      </Card>
    </Space>
  );
};
