import { CheckOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Card, Descriptions, Drawer, Segmented, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import {
  fetchAccountApplications,
  type AccountApplicationRecord,
  updateAccountApplicationStatus,
} from '../../api/modules/auth';
import { useAuthStore } from '../../store/auth';

const statusMap: Record<AccountApplicationRecord['status'], { color: string; text: string }> = {
  pending: { color: 'processing', text: '待审核' },
  approved: { color: 'success', text: '已通过' },
  rejected: { color: 'error', text: '已拒绝' },
};

export const AccountApplicationsPage = () => {
  const [applications, setApplications] = useState<AccountApplicationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<'all' | AccountApplicationRecord['status']>('all');
  const [activeRecord, setActiveRecord] = useState<AccountApplicationRecord | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReviewApplications = hasPermission('account_applications.review');

  const loadApplications = async () => {
    setLoading(true);
    try {
      const data = await fetchAccountApplications();
      setApplications(data.results);
    } catch {
      // 错误已在拦截器中处理，无需重复显示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadApplications();
  }, []);

  const handleAction = async (record: AccountApplicationRecord, status: 'approved' | 'rejected') => {
    setActionLoading(record.id);
    try {
      const response = await updateAccountApplicationStatus(record.id, { status });
      const updatedRecord = response.data;
      if (updatedRecord) {
        setApplications((current) => current.map((item) => (item.id === updatedRecord.id ? updatedRecord : item)));
        setActiveRecord((current) => (current?.id === updatedRecord.id ? updatedRecord : current));
      }
      message.success(response.message || (status === 'approved' ? '已通过申请' : '已拒绝申请'));
    } catch {
      // 错误已在拦截器中处理
    } finally {
      setActionLoading(null);
    }
  };

  const filteredApplications = useMemo(() => {
    if (statusFilter === 'all') {
      return applications;
    }
    return applications.filter((item) => item.status === statusFilter);
  }, [applications, statusFilter]);

  const columns: ColumnsType<AccountApplicationRecord> = [
    {
      title: '登录用户名',
      dataIndex: 'username',
      key: 'username',
      width: 140,
      render: (value: string) => value || '-',
    },
    {
      title: '申请人',
      dataIndex: 'applicantName',
      key: 'applicantName',
      width: 140,
    },
    {
      title: '手机号',
      dataIndex: 'phone',
      key: 'phone',
      width: 140,
    },
    {
      title: '企业名称',
      dataIndex: 'enterpriseName',
      key: 'enterpriseName',
      width: 220,
      render: (value: string) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: AccountApplicationRecord['status']) => (
        <Tag color={statusMap[status].color}>{statusMap[status].text}</Tag>
      ),
    },
    {
      title: '提交时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => setActiveRecord(record)}>
            查看
          </Button>
          {canReviewApplications ? (
            <>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                disabled={record.status !== 'pending'}
                loading={actionLoading === record.id}
                onClick={() => void handleAction(record, 'approved')}
              >
                通过
              </Button>
              <Button
                danger
                icon={<CloseOutlined />}
                disabled={record.status !== 'pending'}
                loading={actionLoading === record.id}
                onClick={() => void handleAction(record, 'rejected')}
              >
                拒绝
              </Button>
            </>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <Typography.Title level={3} className="!mb-1 !text-slate-900">
              账号申请管理
            </Typography.Title>
            <Typography.Text className="!text-slate-500">
              查看前端提交的账号申请，并完成通过或拒绝处理。审核通过后会自动创建登录账号，登录密码为申请人提交时自定义的密码。
            </Typography.Text>
          </div>
          <Space wrap>
            <Segmented
              value={statusFilter}
              onChange={(value) => setStatusFilter(value as 'all' | AccountApplicationRecord['status'])}
              options={[
                { label: '全部', value: 'all' },
                { label: '待审核', value: 'pending' },
                { label: '已通过', value: 'approved' },
                { label: '已拒绝', value: 'rejected' },
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadApplications()}>
              刷新
            </Button>
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={filteredApplications}
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          locale={{ emptyText: '暂无账号申请记录' }}
        />
      </Card>

      <Drawer
        title="申请详情"
        width={520}
        open={!!activeRecord}
        onClose={() => setActiveRecord(null)}
        destroyOnHidden
      >
        {activeRecord ? (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="登录用户名">{activeRecord.username || '-'}</Descriptions.Item>
            <Descriptions.Item label="申请人">{activeRecord.applicantName}</Descriptions.Item>
            <Descriptions.Item label="企业名称">{activeRecord.enterpriseName || '-'}</Descriptions.Item>
            <Descriptions.Item label="手机号">{activeRecord.phone}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusMap[activeRecord.status].color}>{statusMap[activeRecord.status].text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="申请原因">{activeRecord.reason}</Descriptions.Item>
            <Descriptions.Item label="提交时间">{activeRecord.created_at}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{activeRecord.updated_at}</Descriptions.Item>
          </Descriptions>
        ) : null}
      </Drawer>
    </Space>
  );
};
