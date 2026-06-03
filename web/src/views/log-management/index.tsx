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

const fallbackActionText: Record<OperationLogAction, string> = {
  create: '新增数据',
  update: '修改数据',
  delete: '删除数据',
};

const pathDescriptionRules: Array<{
  pattern: RegExp;
  descriptions: Partial<Record<string, string>>;
}> = [
  { pattern: /^\/api\/v1\/tenants\/(?:\d+\/)?$/, descriptions: { POST: '新增公司', PUT: '修改公司', PATCH: '修改公司', DELETE: '删除公司' } },
  { pattern: /^\/api\/v1\/tenants\/\d+\/assign-menus\/$/, descriptions: { POST: '分配公司菜单' } },
  { pattern: /^\/api\/v1\/account-applications\/\d+\/approve\/$/, descriptions: { POST: '通过账号申请' } },
  { pattern: /^\/api\/v1\/account-applications\/\d+\/reject\/$/, descriptions: { POST: '拒绝账号申请' } },
  { pattern: /^\/api\/v1\/devices\/[^/]+\/$/, descriptions: { PUT: '修改设备', PATCH: '修改设备', DELETE: '删除设备' } },
  { pattern: /^\/api\/v1\/device-groups\/(?:\d+\/)?$/, descriptions: { POST: '新增设备分组', PUT: '修改设备分组', PATCH: '修改设备分组', DELETE: '删除设备分组' } },
  { pattern: /^\/api\/v1\/device-applications\/(?:\d+\/)?$/, descriptions: { POST: '新增设备应用', PUT: '修改设备应用', PATCH: '修改设备应用', DELETE: '删除设备应用' } },
  { pattern: /^\/api\/v1\/device-authorization-requests\/[^/]+\/bind\/$/, descriptions: { POST: '绑定设备到公司' } },
  { pattern: /^\/api\/v1\/device-authorization-requests\/[^/]+\/ignore\/$/, descriptions: { POST: '忽略设备授权请求' } },
  { pattern: /^\/api\/v1\/device-authorization-requests\/[^/]+\/authorize\/$/, descriptions: { POST: '再次授权设备' } },
  { pattern: /^\/api\/v1\/device-authorization-requests\/[^/]+\/revoke\/$/, descriptions: { POST: '撤销设备授权' } },
  { pattern: /^\/api\/v1\/resources\/[^/]+\/(?:\d+\/)?$/, descriptions: { POST: '新增资源', PUT: '修改资源', PATCH: '修改资源', DELETE: '删除资源' } },
  { pattern: /^\/api\/v1\/knowledge-base\/(?:\d+\/)?$/, descriptions: { POST: '上传知识库文档', PUT: '修改知识库文档', PATCH: '修改知识库文档', DELETE: '删除知识库文档' } },
  { pattern: /^\/api\/v1\/ai-models\/[^/]+\/(?:\d+\/)?$/, descriptions: { POST: '新增 AI 模型配置', PUT: '修改 AI 模型配置', PATCH: '修改 AI 模型配置', DELETE: '删除 AI 模型配置' } },
  { pattern: /^\/api\/v1\/commands\/[^/]+\/(?:\d+\/)?$/, descriptions: { POST: '新增指令数据', PUT: '修改指令数据', PATCH: '修改指令数据', DELETE: '删除指令数据' } },
];

const describeOperationPath = (path: string, method: string, action: OperationLogAction) => {
  const rule = pathDescriptionRules.find((item) => item.pattern.test(path));
  return rule?.descriptions[method] ?? fallbackActionText[action];
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
        width: '10%',
        render: (value: string) => value || <span className="text-slate-400">匿名</span>,
      },
      {
        title: '所属公司',
        dataIndex: 'tenantName',
        key: 'tenantName',
        width: '10%',
        render: (value: string | null) => value || <span className="text-slate-400">—</span>,
      },
      {
        title: '动作',
        dataIndex: 'action',
        key: 'action',
        width: '8%',
        render: (action: OperationLogAction) => {
          const meta = actionMap[action];
          return <Tag color={meta?.color}>{meta?.text ?? action}</Tag>;
        },
      },
      {
        title: '请求方法',
        dataIndex: 'method',
        key: 'method',
        width: '8%',
        render: (method: string) => <Tag color={methodColorMap[method] ?? 'default'}>{method}</Tag>,
      },
      {
        title: '请求路径',
        dataIndex: 'path',
        key: 'path',
        width: '28%',
        ellipsis: true,
        render: (path: string) => <span className="font-mono text-[13px] text-slate-700">{path}</span>,
      },
      {
        title: '操作说明',
        key: 'description',
        width: '20%',
        render: (_, record) => describeOperationPath(record.path, record.method, record.action),
      },
      {
        title: '状态码',
        dataIndex: 'statusCode',
        key: 'statusCode',
        width: '6%',
        render: (code: number) => <Tag color={statusColor(code)}>{code}</Tag>,
      },
      {
        title: '操作时间',
        dataIndex: 'createdAt',
        key: 'createdAt',
        width: '10%',
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
          tableLayout="fixed"
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
