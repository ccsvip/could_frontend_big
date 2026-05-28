import dayjs from 'dayjs';
import {
  DeleteOutlined,
  EditOutlined,
  FilterOutlined,
  PlusOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createCommandGroup,
  deleteCommandGroup,
  fetchCommandGroups,
  type CommandGroupListQuery,
  type CommandGroupPayload,
  type CommandGroupRecord,
  updateCommandGroup,
} from '../../api/modules/commands';
import { useAuthStore } from '../../store/auth';

type CommandGroupFormValues = CommandGroupPayload;

const groupTypeOptions = [
  { label: '控制指令', value: 'control' },
  { label: '任务指令', value: 'task' },
] as const;

const activeOptions = [
  { label: '全部状态', value: 'all' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
] as const;

export const CommandGroupManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('commands.groups.create');
  const canUpdate = hasPermission('commands.groups.update');
  const canDelete = hasPermission('commands.groups.delete');

  const [items, setItems] = useState<CommandGroupRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [groupType, setGroupType] = useState<CommandGroupListQuery['groupType']>('all');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [editingItem, setEditingItem] = useState<CommandGroupRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<CommandGroupFormValues>();

  const query = useMemo<CommandGroupListQuery>(() => ({ page, keyword, groupType, isActive }), [groupType, isActive, keyword, page]);

  const loadData = useCallback(async (nextQuery: CommandGroupListQuery = query) => {
    setLoading(true);
    try {
      const response = await fetchCommandGroups(nextQuery);
      setItems(response.results);
      setTotal(response.count);
    } catch {
      // handled by interceptor
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
    form.setFieldsValue({ groupType: 'control', exportEnabled: false, isActive: true });
    setFormVisible(true);
  };

  const openEditModal = (item: CommandGroupRecord) => {
    setEditingItem(item);
    form.setFieldsValue({
      name: item.name,
      groupType: item.groupType,
      exportEnabled: item.exportEnabled,
      isActive: item.isActive,
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
    setGroupType('all');
    setIsActive('all');
    setPage(1);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: CommandGroupPayload = {
        name: values.name.trim(),
        groupType: values.groupType,
        exportEnabled: values.exportEnabled,
        isActive: values.isActive,
      };

      if (editingItem) {
        await updateCommandGroup(editingItem.id, payload);
      } else {
        await createCommandGroup(payload);
      }

      closeFormModal();
      if (!editingItem) setPage(1);
      void loadData(editingItem ? query : { ...query, page: 1 });
    } catch {
      // handled by interceptor
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (item: CommandGroupRecord) => {
    try {
      await deleteCommandGroup(item.id);
      if (items.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        void loadData();
      }
    } catch {
      // handled by interceptor
    }
  };

  const columns: ColumnsType<CommandGroupRecord> = [
    { title: '指令管理名称', dataIndex: 'name', key: 'name', width: 220 },
    { title: '类型', dataIndex: 'groupTypeLabel', key: 'groupTypeLabel', width: 120, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: '允许导出', dataIndex: 'exportEnabled', key: 'exportEnabled', width: 110, render: (value: boolean) => <Tag color={value ? 'gold' : 'default'}>{value ? '是' : '否'}</Tag> },
    { title: '状态', dataIndex: 'isActive', key: 'isActive', width: 90, render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag> },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180, render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_, item) => (
        <Space size={4}>
          {canUpdate ? <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(item)}>编辑</Button> : null}
          {canDelete ? (
            <Popconfirm title="确认删除该指令管理吗？" onConfirm={() => void handleDelete(item)}>
              <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <Space size={10} align="center">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-teal-50 to-teal-100/60 text-teal-700">
              <ThunderboltOutlined className="text-xl" />
            </div>
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">指令管理</Typography.Title>
              <Typography.Text className="!text-slate-500">维护控制指令与任务指令的分组、导出开关和启用状态。</Typography.Text>
            </div>
          </Space>
          <Space wrap>
            <Input allowClear value={keywordInput} placeholder="搜索指令管理名称" onChange={(event) => setKeywordInput(event.target.value)} onPressEnter={applyFilters} className="!w-64" />
            <Select value={groupType} options={[{ label: '全部类型', value: 'all' }, ...groupTypeOptions]} onChange={(value) => { setGroupType(value as CommandGroupListQuery['groupType']); setPage(1); }} className="!w-32" />
            <Select value={isActive} options={activeOptions as unknown as { label: string; value: string }[]} onChange={(value) => { setIsActive(value as 'all' | 'active' | 'inactive'); setPage(1); }} className="!w-32" />
            <Button type="primary" icon={<FilterOutlined />} onClick={applyFilters}>筛选</Button>
            <Button onClick={resetFilters}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>
            {canCreate ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新增</Button> : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table rowKey="id" loading={loading} columns={columns} dataSource={items} scroll={{ x: 980 }} pagination={{ current: page, pageSize, total, showSizeChanger: false, onChange: (nextPage) => setPage(nextPage) }} locale={{ emptyText: <Empty description="暂无指令管理数据" /> }} />
      </Card>

      <Modal title={editingItem ? '编辑指令管理' : '新增指令管理'} open={formVisible} onCancel={closeFormModal} onOk={() => void handleSubmit()} confirmLoading={submitting} destroyOnHidden forceRender centered okText={editingItem ? '保存' : '创建'} cancelText="取消" width={640}>
        <Form<CommandGroupFormValues> form={form} layout="vertical">
          <Form.Item label="指令管理名称" name="name" rules={[{ required: true, message: '请输入指令管理名称' }]}><Input /></Form.Item>
          <Form.Item label="指令类型" name="groupType" rules={[{ required: true, message: '请选择指令类型' }]}><Select options={groupTypeOptions as unknown as { label: string; value: string }[]} /></Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="是否允许导出" name="exportEnabled" valuePropName="checked"><Switch checkedChildren="允许" unCheckedChildren="禁止" /></Form.Item>
            <Form.Item label="是否启用" name="isActive" valuePropName="checked"><Switch checkedChildren="启用" unCheckedChildren="停用" /></Form.Item>
          </div>
        </Form>
      </Modal>
    </Space>
  );
};
