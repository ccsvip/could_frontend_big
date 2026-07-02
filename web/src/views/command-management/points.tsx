import dayjs from 'dayjs';
import {
  IconTrash,
  IconEdit,
  IconMapPin,
  IconFilter,
  IconPlus,
  IconReload,
} from '@tabler/icons-react';
import { Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createPoint,
  deletePoint,
  fetchPoints,
  type PointListQuery,
  type PointPayload,
  type PointRecord,
  updatePoint,
} from '../../api/modules/point-management';
import { useAuthStore } from '../../store/auth';

type PointFormValues = PointPayload;

const activeOptions = [
  { label: '全部状态', value: 'all' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
] as const;

export const PointManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('commands.points.create');
  const canUpdate = hasPermission('commands.points.update');
  const canDelete = hasPermission('commands.points.delete');

  const [items, setItems] = useState<PointRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [editingItem, setEditingItem] = useState<PointRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<PointFormValues>();

  const query = useMemo<PointListQuery>(
    () => ({ page, keyword, isActive, includeHidden: true }),
    [isActive, keyword, page],
  );

  const loadData = useCallback(async (nextQuery: PointListQuery = query) => {
    setLoading(true);
    try {
      const response = await fetchPoints(nextQuery);
      setItems(response.results);
      setTotal(response.count);
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ isActive: true, isShow: true } as Partial<PointFormValues>);
    setFormVisible(true);
  };

  const openEditModal = (item: PointRecord) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      command: item.command,
      isActive: item.isActive,
      isShow: item.isShow,
    });
    setFormVisible(true);
  };

  const closeFormModal = () => {
    setFormVisible(false);
    setEditingItem(null);
    form.resetFields();
  };

  const applyFilters = () => {
    setKeyword(keywordInput.trim());
    setPage(1);
  };

  const resetFilters = () => {
    setKeyword('');
    setKeywordInput('');
    setIsActive('all');
    setPage(1);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: PointPayload = {
        name: values.name.trim(),
        command: values.command.trim(),
        isActive: values.isActive,
        isShow: values.isShow,
      };

      if (editingItem) {
        await updatePoint(editingItem.id, payload);
      } else {
        await createPoint(payload);
      }

      closeFormModal();
      if (!editingItem) setPage(1);
      void loadData(editingItem ? query : { ...query, page: 1 });
    } catch {
      // 表单校验和请求错误都在 Ant Design/拦截器中展示。
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (item: PointRecord) => {
    try {
      await deletePoint(item.id);
      if (items.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        void loadData();
      }
    } catch {
      // 请求错误由全局拦截器统一提示。
    }
  };

  const handleToggleShow = async (item: PointRecord, nextValue: boolean) => {
    // 乐观更新：先把开关切到目标态，避免双向 toggle 抖动；失败时回滚并重新拉取以同步真实状态。
    setItems((current) => current.map((row) => (row.id === item.id ? { ...row, isShow: nextValue } : row)));
    try {
      await updatePoint(item.id, { isShow: nextValue });
    } catch {
      setItems((current) => current.map((row) => (row.id === item.id ? { ...row, isShow: !nextValue } : row)));
      void loadData();
    }
  };

  const columns: ColumnsType<PointRecord> = [
    { title: '点位名称', dataIndex: 'name', key: 'name', width: 220 },
    { title: '点位命令', dataIndex: 'command', key: 'command', width: 220, render: (value: string) => <Typography.Text copyable>{value}</Typography.Text> },
    { title: '状态', dataIndex: 'isActive', key: 'isActive', width: 90, render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag> },
    {
      title: '是否显示到前端',
      dataIndex: 'isShow',
      key: 'isShow',
      width: 140,
      render: (value: boolean, item) => (
        <Switch
          checked={value}
          checkedChildren="显示"
          unCheckedChildren="隐藏"
          disabled={!canUpdate}
          onChange={(next) => void handleToggleShow(item, next)}
        />
      ),
    },
    { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt', width: 180, render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_, item) => (
        <Space size={4}>
          {canUpdate ? <Button type="text" icon={<IconEdit />} onClick={() => openEditModal(item)}>编辑</Button> : null}
          {canDelete ? (
            <Popconfirm title="确认删除该点位吗？" onConfirm={() => void handleDelete(item)}>
              <Button type="text" danger icon={<IconTrash />}>删除</Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <Space size={10} align="center">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
              <IconMapPin className="text-xl" />
            </div>
            <div>
              <Typography.Title level={3} className="mb-1 text-slate-900">点位管理</Typography.Title>
              <Typography.Text className="text-slate-500">点位只维护名称、点位命令和启用状态；点位命令是前端运行时传入后端的参数。</Typography.Text>
            </div>
          </Space>
          <Space wrap>
            <Input allowClear value={keywordInput} placeholder="搜索点位名称 / 点位命令" onChange={(event) => setKeywordInput(event.target.value)} onPressEnter={applyFilters} className="w-full sm:w-64" />
            <Select value={isActive} options={activeOptions as unknown as { label: string; value: string }[]} onChange={(value) => { setIsActive(value as 'all' | 'active' | 'inactive'); setPage(1); }} className="w-32" />
            <Button type="primary" icon={<IconFilter />} onClick={applyFilters}>筛选</Button>
            <Button onClick={resetFilters}>重置</Button>
            <Button icon={<IconReload />} onClick={() => void loadData()}>刷新</Button>
            {canCreate ? <Button type="primary" icon={<IconPlus />} onClick={openCreateModal}>新增点位</Button> : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 860 }}
          pagination={{ current: page, pageSize, total, showSizeChanger: false, onChange: (nextPage) => setPage(nextPage) }}
          locale={{ emptyText: <Empty description="暂无点位数据" /> }}
        />
      </Card>

      <Modal title={editingItem ? '编辑点位' : '新增点位'} open={formVisible} onCancel={closeFormModal} onOk={() => void handleSubmit()} confirmLoading={submitting} destroyOnHidden forceRender centered okText={editingItem ? '保存' : '创建'} cancelText="取消" width={600}>
        <Form<PointFormValues> form={form} layout="vertical">
          <Form.Item label="点位名称" name="name" rules={[{ required: true, message: '请输入点位名称' }]}><Input /></Form.Item>
          <Form.Item label="点位命令" name="command" rules={[{ required: true, message: '请输入点位命令' }]}><Input /></Form.Item>
          <Form.Item label="是否启用" name="isActive" valuePropName="checked"><Switch checkedChildren="启用" unCheckedChildren="停用" /></Form.Item>
          <Form.Item label="是否显示到前端" name="isShow" valuePropName="checked"><Switch checkedChildren="显示" unCheckedChildren="隐藏" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
