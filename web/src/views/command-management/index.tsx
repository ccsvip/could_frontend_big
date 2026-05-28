import dayjs from 'dayjs';
import {
  DeleteOutlined,
  EditOutlined,
  FilterOutlined,
  PlusOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createControlCommand,
  deleteControlCommand,
  fetchCommandGroups,
  fetchControlCommands,
  type CommandCallMethod,
  type CommandValueType,
  type CommandGroupRecord,
  type ControlCommandListQuery,
  type ControlCommandPayload,
  type ControlCommandRecord,
  updateControlCommand,
} from '../../api/modules/commands';
import { useAuthStore } from '../../store/auth';

type ControlCommandFormValues = ControlCommandPayload;

const activeOptions = [
  { label: '全部状态', value: 'all' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
] as const;

const callMethodOptions: Array<{ label: string; value: CommandCallMethod }> = [
  { label: 'UDP', value: 'UDP' },
  // { label: 'TCP', value: 'TCP' },
];

const commandValueTypeOptions: Array<{ label: string; value: CommandValueType }> = [
  { label: '字符串', value: 'string' },
  { label: '16进制', value: 'hex' },
  { label: 'ascii', value: 'ascii' },
];

const commandValueTypeLabels: Record<CommandValueType, string> = {
  string: '字符串',
  hex: '16进制',
  ascii: 'ascii',
};

export const ControlCommandManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('commands.control.create');
  const canUpdate = hasPermission('commands.control.update');
  const canDelete = hasPermission('commands.control.delete');

  const [items, setItems] = useState<ControlCommandRecord[]>([]);
  const [groups, setGroups] = useState<CommandGroupRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [groupId, setGroupId] = useState<number | 'all'>('all');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [editingItem, setEditingItem] = useState<ControlCommandRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<ControlCommandFormValues>();

  const query = useMemo<ControlCommandListQuery>(
    () => ({ page, keyword, groupId, isActive }),
    [groupId, isActive, keyword, page],
  );

  const loadData = useCallback(async (nextQuery: ControlCommandListQuery = query) => {
    setLoading(true);
    try {
      const response = await fetchControlCommands(nextQuery);
      setItems(response.results);
      setTotal(response.count);
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setLoading(false);
    }
  }, [query]);

  const loadGroups = useCallback(async () => {
    try {
      const response = await fetchCommandGroups({ groupType: 'control', isActive: 'active' });
      setGroups(response.results);
    } catch {
      setGroups([]);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({
      groupId: groups[0]?.id,
      commandValueType: 'string',
      callMethod: 'UDP',
      isActive: true,
    } as Partial<ControlCommandFormValues>);
    setFormVisible(true);
  };

  const openEditModal = (item: ControlCommandRecord) => {
    setEditingItem(item);
    form.setFieldsValue({
      groupId: item.groupId,
      name: item.name,
      command: item.command,
      commandValueType: item.commandValueType ?? 'string',
      ip: item.ip,
      port: item.port,
      callMethod: item.callMethod,
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
    setGroupId('all');
    setIsActive('all');
    setPage(1);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: ControlCommandPayload = {
        groupId: values.groupId,
        name: values.name.trim(),
        command: values.command.trim(),
        commandValueType: values.commandValueType ?? 'string',
        ip: values.ip.trim(),
        port: Number(values.port),
        callMethod: values.callMethod,
        isActive: values.isActive,
      };

      if (editingItem) {
        await updateControlCommand(editingItem.id, payload);
      } else {
        await createControlCommand(payload);
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

  const handleDelete = async (item: ControlCommandRecord) => {
    try {
      await deleteControlCommand(item.id);
      if (items.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        void loadData();
      }
    } catch {
      // 请求错误由全局拦截器统一提示。
    }
  };

  const groupOptions = useMemo(
    () => groups.map((item) => ({ label: item.name, value: item.id })),
    [groups],
  );

  const columns: ColumnsType<ControlCommandRecord> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
    { title: '所属指令管理', dataIndex: 'groupName', key: 'groupName', width: 180, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: '指令', dataIndex: 'command', key: 'command', width: 180, render: (value: string) => <Typography.Text copyable>{value}</Typography.Text> },
    {
      title: '调用方式',
      key: 'network',
      width: 240,
      render: (_, item) => (
        <Space size={6} wrap>
          <Tag color={item.callMethod === 'UDP' ? 'cyan' : 'geekblue'}>{item.callMethod}</Tag>
          <Tag color="purple">{commandValueTypeLabels[item.commandValueType ?? 'string']}</Tag>
          <Typography.Text>{item.ip}:{item.port}</Typography.Text>
        </Space>
      ),
    },
    { title: '状态', dataIndex: 'isActive', key: 'isActive', width: 90, render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag> },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180, render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_, item) => (
        <Space size={4}>
          {canUpdate ? <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(item)}>编辑</Button> : null}
          {canDelete ? (
            <Popconfirm title="确认删除该控制指令吗？" onConfirm={() => void handleDelete(item)}>
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
              <Typography.Title level={3} className="!mb-1 !text-slate-900">控制指令</Typography.Title>
              <Typography.Text className="!text-slate-500">维护中控可执行指令、网络地址、端口和 UDP/TCP 调用方式。</Typography.Text>
            </div>
          </Space>
          <Space wrap>
            <Input allowClear value={keywordInput} placeholder="搜索名称 / 指令" onChange={(event) => setKeywordInput(event.target.value)} onPressEnter={applyFilters} className="!w-64" />
            <Select value={groupId} options={[{ label: '全部指令管理', value: 'all' }, ...groupOptions]} onChange={(value) => { setGroupId(value as number | 'all'); setPage(1); }} className="!w-40" />
            <Select value={isActive} options={activeOptions as unknown as { label: string; value: string }[]} onChange={(value) => { setIsActive(value as 'all' | 'active' | 'inactive'); setPage(1); }} className="!w-32" />
            <Button type="primary" icon={<FilterOutlined />} onClick={applyFilters}>筛选</Button>
            <Button onClick={resetFilters}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>
            {canCreate ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新增指令</Button> : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1120 }}
          pagination={{ current: page, pageSize, total, showSizeChanger: false, onChange: (nextPage) => setPage(nextPage) }}
          locale={{ emptyText: <Empty description="暂无控制指令数据" /> }}
        />
      </Card>

      <Modal title={editingItem ? '编辑控制指令' : '新增控制指令'} open={formVisible} onCancel={closeFormModal} onOk={() => void handleSubmit()} confirmLoading={submitting} destroyOnHidden forceRender centered okText={editingItem ? '保存' : '创建'} cancelText="取消" width={720}>
        <Form<ControlCommandFormValues> form={form} layout="vertical">
          <Form.Item label="所属指令管理" name="groupId" rules={[{ required: true, message: '请选择控制指令类型的指令管理' }]}>
            <Select options={groupOptions} placeholder="请选择指令管理" />
          </Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
            <Form.Item label="指令" name="command" rules={[{ required: true, message: '请输入指令' }]}><Input /></Form.Item>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_120px_120px_130px]">
            <Form.Item label="IP" name="ip" rules={[{ required: true, message: '请输入 IP' }]}><Input placeholder="192.168.1.10" /></Form.Item>
            <Form.Item label="端口" name="port" rules={[{ required: true, message: '请输入端口' }]}><InputNumber min={1} max={65535} precision={0} className="!w-full" /></Form.Item>
            <Form.Item label="调用方式" name="callMethod" rules={[{ required: true, message: '请选择调用方式' }]}><Select options={callMethodOptions} /></Form.Item>
            <Form.Item label="指令类型" name="commandValueType" rules={[{ required: true, message: '请选择指令类型' }]}><Select options={commandValueTypeOptions} /></Form.Item>
          </div>
          <Form.Item label="是否启用" name="isActive" valuePropName="checked"><Switch checkedChildren="启用" unCheckedChildren="停用" /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export const CommandManagementPage = ControlCommandManagementPage;
