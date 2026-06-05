import { DeleteOutlined, FileSearchOutlined } from '@ant-design/icons';
import { Button, Card, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  clearOperationLogs,
  fetchOperationLogs,
  type OperationLogAction,
  type OperationLogRecord,
} from '../../api/modules/audit';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import { useAuthStore } from '../../store/auth';

const PAGE_SIZE = 10;

const actionMap: Record<OperationLogAction, { color: string; text: string }> = {
  create: { color: 'success', text: '新增' },
  update: { color: 'processing', text: '修改' },
  delete: { color: 'error', text: '删除' },
};

export const LogManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const tenant = useAuthStore((state) => state.tenant);
  const isPlatformAdmin = hasPermission('tenant.management.view') || !tenant;
  const [logs, setLogs] = useState<OperationLogRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
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
    if (!isPlatformAdmin || hasLoadedTenantsRef.current) {
      return;
    }
    hasLoadedTenantsRef.current = true;
    void (async () => {
      try {
        const data = await fetchTenants({ page_size: 100 });
        setTenants(data.results);
      } catch {
        // 错误已在拦截器中处理
      }
    })();
  }, [isPlatformAdmin]);

  const handleClearLogs = () => {
    Modal.confirm({
      title: '清空日志',
      content: isPlatformAdmin
        ? '将真实删除全平台全部操作日志，无法恢复。'
        : '将真实删除当前公司全部操作日志，无法恢复。',
      okText: '确认清空',
      okButtonProps: { danger: true, loading: clearing },
      cancelText: '取消',
      async onOk() {
        setClearing(true);
        try {
          const data = await clearOperationLogs();
          message.success(`已清空 ${data.deleted} 条日志`);
          setTenantFilter(undefined);
          setPage(1);
          await loadLogs(1, undefined);
        } finally {
          setClearing(false);
        }
      },
    });
  };

  const columns: ColumnsType<OperationLogRecord> = useMemo(
    () => [
      {
        title: '操作人',
        dataIndex: 'actorUsername',
        key: 'actorUsername',
        width: '20%',
        render: (value: string) => value || <span className="text-slate-400">匿名</span>,
      },
      {
        title: '动作',
        dataIndex: 'action',
        key: 'action',
        width: '14%',
        render: (action: OperationLogAction) => {
          const meta = actionMap[action];
          return <Tag color={meta?.color}>{meta?.text ?? action}</Tag>;
        },
      },
      {
        title: '操作具体做了什么',
        dataIndex: 'description',
        key: 'description',
        width: '46%',
        ellipsis: true,
        render: (value: string) => value || <span className="text-slate-400">-</span>,
      },
      {
        title: '时间',
        dataIndex: 'createdAt',
        key: 'createdAt',
        width: '20%',
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
            <Typography.Title level={4} className="!mb-1 !font-semibold !text-slate-900">
              操作日志审计
            </Typography.Title>
            <Typography.Text className="!text-[13px] !text-slate-500">
              记录平台内各公司的写操作（新增 / 修改 / 删除），可按公司筛选追溯。
            </Typography.Text>
          </div>
          <Space className="!w-full justify-end md:!w-auto">
            {isPlatformAdmin ? (
              <Select
                allowClear
                placeholder="按公司筛选"
                className="!w-60"
                value={tenantFilter}
                onChange={(value) => {
                  setTenantFilter(value);
                  setPage(1);
                }}
                options={tenants.map((tenantItem) => ({ value: tenantItem.id, label: tenantItem.name }))}
              />
            ) : null}
            <Button danger icon={<DeleteOutlined />} loading={clearing} onClick={handleClearLogs}>
              清空日志
            </Button>
          </Space>
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
