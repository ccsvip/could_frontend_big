import dayjs from 'dayjs';
import {
  IconTrash,
  IconEdit,
  IconFilter,
  IconMenu2,
  IconPlus,
  IconReload,
} from '@tabler/icons-react';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
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
  createTaskCommand,
  deleteTaskCommand,
  fetchCommandGroups,
  fetchControlCommands,
  fetchTaskCommands,
  type CommandGroupRecord,
  type ControlCommandRecord,
  type TaskCommandListQuery,
  type TaskCommandPayload,
  type TaskCommandRecord,
  updateTaskCommand,
} from '../../api/modules/commands';
import { fetchPoints, type PointRecord } from '../../api/modules/point-management';
import { fetchImageResources, fetchVideoResources, type ResourceRecord } from '../../api/modules/resources';
import { useAuthStore } from '../../store/auth';
import {
  buildStepPayload,
  mapStepRecordToFormValue,
  TaskStepFormList,
  taskCommandModalBodyStyle,
  taskCommandModalClassName,
  taskTypeColors,
  taskTypeLabels,
  type TaskCommandFormValues,
} from './task-step-form-list';

const activeOptions = [
  { label: '全部状态', value: 'all' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
] as const;

const collectPages = async <T,>(fetcher: (page: number) => Promise<{ next: string | null; results: T[] }>) => {
  const results: T[] = [];
  let page = 1;
  let hasNext = true;
  while (hasNext) {
    const response = await fetcher(page);
    results.push(...response.results);
    hasNext = Boolean(response.next);
    page += 1;
  }
  return results;
};

const getStepSummary = (step: TaskCommandRecord['tasks'][number]) => {
  const content = step.content || {};
  if (step.type === 'text') return String(content.text || step.text || '-');
  if (step.type === 'command') return `${String(content.name || '-')}: ${String(content.command || '-')}`;
  if (step.type === 'navigation') return `${String(content.pointName || content.name || '-')}: ${String(content.command || '-')}`;
  const mediaName = `${String(content.name || '-')} ${content.fileName ? `(${String(content.fileName)})` : ''}`;
  if (step.type === 'image') {
    const imageText = String(step.imageText || content.imageText || '');
    return imageText ? `${mediaName} - ${imageText}` : mediaName;
  }
  return mediaName;
};

export const TaskCommandManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('commands.tasks.create');
  const canUpdate = hasPermission('commands.tasks.update');
  const canDelete = hasPermission('commands.tasks.delete');

  const [items, setItems] = useState<TaskCommandRecord[]>([]);
  const [groups, setGroups] = useState<CommandGroupRecord[]>([]);
  const [controlCommands, setControlCommands] = useState<ControlCommandRecord[]>([]);
  const [points, setPoints] = useState<PointRecord[]>([]);
  const [imageResources, setImageResources] = useState<ResourceRecord[]>([]);
  const [videoResources, setVideoResources] = useState<ResourceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [groupId, setGroupId] = useState<number | 'all'>('all');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [editingItem, setEditingItem] = useState<TaskCommandRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<TaskCommandFormValues>();

  const query = useMemo<TaskCommandListQuery>(
    () => ({ page, keyword, groupId, isActive }),
    [groupId, isActive, keyword, page],
  );

  const loadData = useCallback(async (nextQuery: TaskCommandListQuery = query) => {
    setLoading(true);
    try {
      const response = await fetchTaskCommands(nextQuery);
      setItems(response.results);
      setTotal(response.count);
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setLoading(false);
    }
  }, [query]);

  const loadLookups = useCallback(async () => {
    setLookupLoading(true);
    try {
      const [groupResponse, commandResults, pointResults, imageResults, videoResults] = await Promise.all([
        fetchCommandGroups({ groupType: 'task', isActive: 'active' }),
        collectPages<ControlCommandRecord>((nextPage) => fetchControlCommands({ page: nextPage, isActive: 'active' })),
        collectPages<PointRecord>((nextPage) => fetchPoints({ page: nextPage, isActive: 'active' })),
        collectPages<ResourceRecord>((nextPage) => fetchImageResources({ page: nextPage })),
        collectPages<ResourceRecord>((nextPage) => fetchVideoResources({ page: nextPage })),
      ]);
      setGroups(groupResponse.results);
      setControlCommands(commandResults);
      setPoints(pointResults);
      setImageResources(imageResults);
      setVideoResources(videoResults);
    } catch {
      setGroups([]);
      setControlCommands([]);
      setPoints([]);
      setImageResources([]);
      setVideoResources([]);
    } finally {
      setLookupLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({
      groupId: groups[0]?.id,
      isActive: true,
      tasks: [{ type: 'text', text: '', delaySeconds: 0 }],
    } as TaskCommandFormValues);
    setFormVisible(true);
  };

  const openEditModal = (item: TaskCommandRecord) => {
    setEditingItem(item);
    form.setFieldsValue({
      groupId: item.groupId,
      name: item.name,
      command: item.command,
      isActive: item.isActive,
      tasks: item.tasks.map(mapStepRecordToFormValue),
    });
    setFormVisible(true);
  };

  const closeFormModal = () => {
    setFormVisible(false);
  };

  const cleanupFormModal = () => {
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
      const payload: TaskCommandPayload = {
        groupId: values.groupId,
        name: values.name.trim(),
        command: values.command.trim(),
        isActive: values.isActive,
        tasks: values.tasks.map(buildStepPayload),
      };

      if (editingItem) {
        await updateTaskCommand(editingItem.id, payload);
      } else {
        await createTaskCommand(payload);
      }

      const wasEditing = Boolean(editingItem);
      closeFormModal();
      if (!wasEditing) setPage(1);
      void loadData(wasEditing ? query : { ...query, page: 1 });
    } catch {
      // 表单校验和请求错误都在 Ant Design/拦截器中展示。
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (item: TaskCommandRecord) => {
    try {
      await deleteTaskCommand(item.id);
      if (items.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        void loadData();
      }
    } catch {
      // 请求错误由全局拦截器统一提示。
    }
  };

  const groupOptions = useMemo(() => groups.map((item) => ({ label: item.name, value: item.id })), [groups]);
  const controlCommandOptions = useMemo(
    () => controlCommands.map((item) => ({ label: `${item.name} (${item.command})`, value: item.id })),
    [controlCommands],
  );
  const pointOptions = useMemo(
    () => points.map((item) => ({ label: `${item.name} (${item.command})`, value: item.id })),
    [points],
  );
  const imageOptions = useMemo(
    () => imageResources.map((item) => ({ label: `${item.name}${item.fileName ? ` (${item.fileName})` : ''}`, value: item.id })),
    [imageResources],
  );
  const videoOptions = useMemo(
    () => videoResources.map((item) => ({ label: `${item.name}${item.fileName ? ` (${item.fileName})` : ''}`, value: item.id })),
    [videoResources],
  );

  const columns: ColumnsType<TaskCommandRecord> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 180 },
    { title: '所属指令管理', dataIndex: 'groupName', key: 'groupName', width: 180, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: '指令名称', dataIndex: 'command', key: 'command', width: 180, render: (value: string) => <Typography.Text copyable>{value}</Typography.Text> },
    {
      title: '子任务',
      key: 'tasks',
      width: 420,
      render: (_, item) => (
        <Space direction="vertical" size={4}>
          {item.tasks.map((step) => (
            <Space key={step.id} size={6} wrap>
              <Tag color={taskTypeColors[step.type]}>{step.order}. {taskTypeLabels[step.type]}</Tag>
              <Tag color="cyan">延迟 {step.delaySeconds ?? 0} 秒</Tag>
              <Typography.Text className="!text-slate-600">{getStepSummary(step)}</Typography.Text>
            </Space>
          ))}
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
          {canUpdate ? <Button type="text" icon={<IconEdit />} onClick={() => openEditModal(item)}>编辑</Button> : null}
          {canDelete ? (
            <Popconfirm title="确认删除该任务指令吗？" onConfirm={() => void handleDelete(item)}>
              <Button type="text" danger icon={<IconTrash />}>删除</Button>
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
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <IconMenu2 className="text-xl" />
            </div>
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">任务指令</Typography.Title>
              <Typography.Text className="!text-slate-500">维护场景任务编排，子任务可选择指令、文本、图片、视频或导航点位。</Typography.Text>
            </div>
          </Space>
          <Space wrap>
            <Input allowClear value={keywordInput} placeholder="搜索名称 / 指令名称" onChange={(event) => setKeywordInput(event.target.value)} onPressEnter={applyFilters} className="w-full sm:w-64" />
            <Select value={groupId} options={[{ label: '全部指令管理', value: 'all' }, ...groupOptions]} onChange={(value) => { setGroupId(value as number | 'all'); setPage(1); }} className="!w-40" />
            <Select value={isActive} options={activeOptions as unknown as { label: string; value: string }[]} onChange={(value) => { setIsActive(value as 'all' | 'active' | 'inactive'); setPage(1); }} className="!w-32" />
            <Button type="primary" icon={<IconFilter />} onClick={applyFilters}>筛选</Button>
            <Button onClick={resetFilters}>重置</Button>
            <Button icon={<IconReload />} onClick={() => void loadData()}>刷新</Button>
            {canCreate ? <Button type="primary" icon={<IconPlus />} onClick={openCreateModal}>新增任务指令</Button> : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1240 }}
          pagination={{ current: page, pageSize, total, showSizeChanger: false, onChange: (nextPage) => setPage(nextPage) }}
          locale={{ emptyText: <Empty description="暂无任务指令数据" /> }}
        />
      </Card>

      <Modal title={editingItem ? '编辑任务指令' : '新增任务指令'} open={formVisible} onCancel={closeFormModal} afterOpenChange={(open) => { if (!open) cleanupFormModal(); }} onOk={() => void handleSubmit()} confirmLoading={submitting} destroyOnHidden forceRender centered okText={editingItem ? '保存' : '创建'} cancelText="取消" width={960} className={taskCommandModalClassName} styles={{ body: taskCommandModalBodyStyle }}>
        <Form<TaskCommandFormValues> form={form} layout="vertical">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="所属指令管理" name="groupId" rules={[{ required: true, message: '请选择任务指令类型的指令管理' }]}>
              <Select loading={lookupLoading} options={groupOptions} placeholder="请选择指令管理" />
            </Form.Item>
            <Form.Item label="是否启用" name="isActive" valuePropName="checked"><Switch checkedChildren="启用" unCheckedChildren="停用" /></Form.Item>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input placeholder="例如：场景任务编排" /></Form.Item>
            <Form.Item label="指令名称" name="command" rules={[{ required: true, message: '请输入指令名称' }]}><Input placeholder="例如：WELCOME_SCENE" /></Form.Item>
          </div>

          <TaskStepFormList
            lookupLoading={lookupLoading}
            controlCommandOptions={controlCommandOptions}
            pointOptions={pointOptions}
            imageOptions={imageOptions}
            videoOptions={videoOptions}
          />
        </Form>
      </Modal>
    </Space>
  );
};
