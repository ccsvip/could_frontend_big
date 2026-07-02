import {
  IconTrash,
  IconDownload,
  IconEdit,
  IconPlus,
  IconReload,
  IconUpload,
} from '@tabler/icons-react';
import {
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Pagination,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
} from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  createCommandGroup,
  createControlCommand,
  createTaskCommand,
  deleteCommandGroup,
  deleteControlCommand,
  deleteTaskCommand,
  fetchCommandGroups,
  fetchControlCommands,
  fetchTaskCommands,
  type CommandCallMethod,
  type CommandValueType,
  type CommandGroupPayload,
  type CommandGroupRecord,
  type ControlCommandPayload,
  type ControlCommandRecord,
  type PaginatedResponse,
  type TaskCommandPayload,
  type TaskCommandRecord,
  type TaskCommandStepPayload,
  updateCommandGroup,
  updateControlCommand,
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

type CommandGroupFullExportPayload = {
  format: 'command-group-full-v1';
  exportedAt: string;
  group: Pick<CommandGroupRecord, 'name' | 'groupType' | 'exportEnabled' | 'isActive'>;
  controlCommands: ControlCommandRecord[];
  taskCommands: TaskCommandRecord[];
};

type ImportMissingAsset = {
  commandName: string;
  commandCode: string;
  stepOrder: number;
  assetType: string;
  assetName: string;
  action: 'skip-step' | 'skip-command';
};

const groupTypeLabels: Record<CommandGroupRecord['groupType'], string> = {
  control: '控制指令',
  task: '任务指令',
};

const groupTypeColors: Record<CommandGroupRecord['groupType'], string> = {
  control: 'green',
  task: 'orange',
};

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

const COMMAND_CARD_PAGE_SIZE = 8;
const LOOKUP_PAGE_SIZE = 100;
const TASK_LOOKUP_CACHE_TTL_MS = 60_000;

type TaskLookupCollections = {
  controlCommands: ControlCommandRecord[];
  points: PointRecord[];
  imageResources: ResourceRecord[];
  videoResources: ResourceRecord[];
};

let taskLookupCache: { data: TaskLookupCollections; updatedAt: number } | null = null;
let taskLookupRequest: Promise<TaskLookupCollections> | null = null;

const collectPages = async <T,>(fetcher: (page: number) => Promise<Pick<PaginatedResponse<T>, 'next' | 'results'>>) => {
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

const fetchTaskLookupsWithCache = async (force = false) => {
  const now = Date.now();
  if (!force && taskLookupCache && now - taskLookupCache.updatedAt < TASK_LOOKUP_CACHE_TTL_MS) {
    return taskLookupCache.data;
  }

  if (!force && taskLookupRequest) {
    return taskLookupRequest;
  }

  taskLookupRequest = Promise.all([
    collectPages<ControlCommandRecord>((page) => fetchControlCommands({ page, pageSize: LOOKUP_PAGE_SIZE, isActive: 'active' })),
    collectPages<PointRecord>((page) => fetchPoints({ page, pageSize: LOOKUP_PAGE_SIZE, isActive: 'active' })),
    collectPages<ResourceRecord>((page) => fetchImageResources({ page, pageSize: LOOKUP_PAGE_SIZE })),
    collectPages<ResourceRecord>((page) => fetchVideoResources({ page, pageSize: LOOKUP_PAGE_SIZE })),
  ]).then(([controlCommands, points, imageResources, videoResources]) => {
    const data = { controlCommands, points, imageResources, videoResources };
    taskLookupCache = { data, updatedAt: Date.now() };
    return data;
  }).finally(() => {
    taskLookupRequest = null;
  });

  return taskLookupRequest;
};

const invalidateTaskLookupCache = () => {
  taskLookupCache = null;
};

const formatTimestamp = () => {
  const date = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
};

const downloadJson = (data: unknown, filename: string) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
};

const isCommandGroupFullExportPayload = (value: unknown): value is CommandGroupFullExportPayload => {
  const payload = value as Partial<CommandGroupFullExportPayload>;
  return (
    Boolean(payload) &&
    payload.format === 'command-group-full-v1' &&
    Boolean(payload.group) &&
    (payload.group?.groupType === 'control' || payload.group?.groupType === 'task') &&
    Array.isArray(payload.controlCommands) &&
    Array.isArray(payload.taskCommands)
  );
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

export const CommandWorkspacePage = () => {
  const location = useLocation();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreateGroup = hasPermission('commands.groups.create');
  const canUpdateGroup = hasPermission('commands.groups.update');
  const canDeleteGroup = hasPermission('commands.groups.delete');
  const canCreateControl = hasPermission('commands.control.create');
  const canUpdateControl = hasPermission('commands.control.update');
  const canDeleteControl = hasPermission('commands.control.delete');
  const canCreateTask = hasPermission('commands.tasks.create');
  const canUpdateTask = hasPermission('commands.tasks.update');
  const canDeleteTask = hasPermission('commands.tasks.delete');
  const canExportCommands = hasPermission('commands.export.download');

  const [groups, setGroups] = useState<CommandGroupRecord[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [groupKeyword, setGroupKeyword] = useState('');
  const [groupsLoading, setGroupsLoading] = useState(false);

  const [controlCommands, setControlCommands] = useState<ControlCommandRecord[]>([]);
  const [taskCommands, setTaskCommands] = useState<TaskCommandRecord[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);
  const [commandKeyword, setCommandKeyword] = useState('');
  const [commandPage, setCommandPage] = useState(1);
  const [commandTotal, setCommandTotal] = useState(0);

  const [controlLookups, setControlLookups] = useState<ControlCommandRecord[]>([]);
  const [points, setPoints] = useState<PointRecord[]>([]);
  const [imageResources, setImageResources] = useState<ResourceRecord[]>([]);
  const [videoResources, setVideoResources] = useState<ResourceRecord[]>([]);
  const [lookupLoading, setLookupLoading] = useState(false);

  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<CommandGroupRecord | null>(null);
  const [controlModalOpen, setControlModalOpen] = useState(false);
  const [editingControl, setEditingControl] = useState<ControlCommandRecord | null>(null);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskCommandRecord | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [transferLoading, setTransferLoading] = useState(false);

  const [groupForm] = Form.useForm<CommandGroupPayload>();
  const [controlForm] = Form.useForm<ControlCommandPayload>();
  const [taskForm] = Form.useForm<TaskCommandFormValues>();

  const routePreferredType = useMemo<CommandGroupRecord['groupType'] | null>(() => {
    if (location.pathname.includes('/commands/control')) return 'control';
    if (location.pathname.includes('/commands/tasks')) return 'task';
    return null;
  }, [location.pathname]);

  const selectedGroup = useMemo(
    () => groups.find((item) => item.id === selectedGroupId) ?? groups[0] ?? null,
    [groups, selectedGroupId],
  );

  const filteredGroups = useMemo(() => {
    const keyword = groupKeyword.trim().toLowerCase();
    if (!keyword) return groups;
    return groups.filter((item) => item.name.toLowerCase().includes(keyword));
  }, [groupKeyword, groups]);

  const paginatedControlCommands = controlCommands;
  const paginatedTaskCommands = taskCommands;

  const loadGroups = useCallback(async (preferredGroupId?: number) => {
    setGroupsLoading(true);
    try {
      const nextGroups = await collectPages<CommandGroupRecord>((page) => fetchCommandGroups({ page, pageSize: LOOKUP_PAGE_SIZE, isActive: 'all' }));
      setGroups(nextGroups);
      const stillExists = preferredGroupId ? nextGroups.some((item) => item.id === preferredGroupId) : false;
      const routePreferredGroup = routePreferredType ? nextGroups.find((item) => item.groupType === routePreferredType) : null;
      setCommandPage(1);
      setSelectedGroupId(stillExists ? preferredGroupId! : routePreferredGroup?.id ?? nextGroups[0]?.id ?? null);
    } catch {
      setGroups([]);
      setSelectedGroupId(null);
      setCommandTotal(0);
    } finally {
      setGroupsLoading(false);
    }
  }, [routePreferredType]);

  const loadCommands = useCallback(async (
    group: CommandGroupRecord | null,
    options: { page?: number; keyword?: string } = {},
  ) => {
    if (!group) {
      setControlCommands([]);
      setTaskCommands([]);
      setCommandTotal(0);
      return;
    }

    const page = options.page ?? 1;
    const keyword = options.keyword?.trim() || undefined;

    setCommandsLoading(true);
    try {
      if (group.groupType === 'control') {
        const response = await fetchControlCommands({ page, pageSize: COMMAND_CARD_PAGE_SIZE, keyword, groupId: group.id, isActive: 'all' });
        setControlCommands(response.results);
        setTaskCommands([]);
        setCommandTotal(response.count);
      } else {
        const response = await fetchTaskCommands({ page, pageSize: COMMAND_CARD_PAGE_SIZE, keyword, groupId: group.id, isActive: 'all' });
        setTaskCommands(response.results);
        setControlCommands([]);
        setCommandTotal(response.count);
      }
    } catch {
      setControlCommands([]);
      setTaskCommands([]);
      setCommandTotal(0);
    } finally {
      setCommandsLoading(false);
    }
  }, []);

  const loadTaskLookups = useCallback(async (options: { force?: boolean } = {}) => {
    setLookupLoading(true);
    try {
      const lookups = await fetchTaskLookupsWithCache(Boolean(options.force));
      setControlLookups(lookups.controlCommands);
      setPoints(lookups.points);
      setImageResources(lookups.imageResources);
      setVideoResources(lookups.videoResources);
      return lookups;
    } catch {
      setControlLookups([]);
      setPoints([]);
      setImageResources([]);
      setVideoResources([]);
      return null;
    } finally {
      setLookupLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  useEffect(() => {
    void loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
  }, [commandKeyword, commandPage, loadCommands, selectedGroup]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(commandTotal / COMMAND_CARD_PAGE_SIZE));
    if (commandPage > maxPage) {
      setCommandPage(maxPage);
    }
  }, [commandPage, commandTotal]);

  const refreshCurrentGroup = () => {
    void loadGroups(selectedGroup?.id);
  };

  const openCreateGroup = () => {
    setEditingGroup(null);
    groupForm.resetFields();
    groupForm.setFieldsValue({ groupType: 'control', exportEnabled: true, isActive: true });
    setGroupModalOpen(true);
  };

  const openEditGroup = (item: CommandGroupRecord) => {
    setEditingGroup(item);
    groupForm.setFieldsValue({
      name: item.name,
      groupType: item.groupType,
      exportEnabled: item.exportEnabled,
      isActive: item.isActive,
    });
    setGroupModalOpen(true);
  };

  const closeGroupModal = () => {
    setGroupModalOpen(false);
    setEditingGroup(null);
    groupForm.resetFields();
  };

  const saveGroup = async () => {
    try {
      const values = await groupForm.validateFields();
      setSubmitting(true);
      const payload: CommandGroupPayload = {
        name: values.name.trim(),
        groupType: values.groupType,
        exportEnabled: values.exportEnabled,
        isActive: values.isActive,
      };

      const saved = editingGroup
        ? await updateCommandGroup(editingGroup.id, payload)
        : await createCommandGroup(payload);

      closeGroupModal();
      await loadGroups(saved.id);
    } catch {
      // 表单校验和请求错误由 Ant Design 与全局拦截器展示。
    } finally {
      setSubmitting(false);
    }
  };

  const removeGroup = async (item: CommandGroupRecord) => {
    try {
      await deleteCommandGroup(item.id);
      await loadGroups(selectedGroup?.id === item.id ? undefined : selectedGroup?.id);
    } catch {
      // 删除错误由全局拦截器展示。
    }
  };

  const confirmRemoveGroup = (item: CommandGroupRecord) => {
    Modal.confirm({
      title: '确认删除指令管理？',
      content: `删除后将无法在工作台继续维护「${item.name}」，请确认是否继续。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: () => removeGroup(item),
    });
  };

  const openCreateControl = () => {
    if (!selectedGroup || selectedGroup.groupType !== 'control') return;
    setEditingControl(null);
    controlForm.resetFields();
    controlForm.setFieldsValue({
      groupId: selectedGroup.id,
      commandValueType: 'string',
      callMethod: 'UDP',
      isActive: true,
    } as Partial<ControlCommandPayload>);
    setControlModalOpen(true);
  };

  const openEditControl = (item: ControlCommandRecord) => {
    setEditingControl(item);
    controlForm.setFieldsValue({
      groupId: item.groupId,
      name: item.name,
      command: item.command,
      commandValueType: item.commandValueType ?? 'string',
      ip: item.ip,
      port: item.port,
      callMethod: item.callMethod,
      isActive: item.isActive,
    });
    setControlModalOpen(true);
  };

  const closeControlModal = () => {
    setControlModalOpen(false);
    setEditingControl(null);
    controlForm.resetFields();
  };

  const saveControl = async () => {
    try {
      const values = await controlForm.validateFields();
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

      if (editingControl) {
        await updateControlCommand(editingControl.id, payload);
      } else {
        await createControlCommand(payload);
      }

      closeControlModal();
      invalidateTaskLookupCache();
      await loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
    } catch {
      // 表单校验和请求错误由 Ant Design 与全局拦截器展示。
    } finally {
      setSubmitting(false);
    }
  };

  const removeControl = async (item: ControlCommandRecord) => {
    try {
      await deleteControlCommand(item.id);
      invalidateTaskLookupCache();
      await loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
    } catch {
      // 删除错误由全局拦截器展示。
    }
  };

  const confirmRemoveControl = (item: ControlCommandRecord) => {
    Modal.confirm({
      title: '确认删除控制指令？',
      content: `即将删除「${item.name}（${item.command}）」，删除后设备端将无法继续使用该控制指令。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: () => removeControl(item),
    });
  };

  const openCreateTask = () => {
    if (!selectedGroup || selectedGroup.groupType !== 'task') return;
    setEditingTask(null);
    taskForm.resetFields();
    taskForm.setFieldsValue({
      groupId: selectedGroup.id,
      isActive: true,
      tasks: [{ type: 'text', text: '', delaySeconds: 0 }],
    } as TaskCommandFormValues);
    setTaskModalOpen(true);
    void loadTaskLookups();
  };

  const openEditTask = (item: TaskCommandRecord) => {
    setEditingTask(item);
    taskForm.setFieldsValue({
      groupId: item.groupId,
      name: item.name,
      command: item.command,
      isActive: item.isActive,
      tasks: item.tasks.map(mapStepRecordToFormValue),
    });
    setTaskModalOpen(true);
    void loadTaskLookups();
  };

  const openAppendTaskStep = (item: TaskCommandRecord) => {
    setEditingTask(item);
    taskForm.setFieldsValue({
      groupId: item.groupId,
      name: item.name,
      command: item.command,
      isActive: item.isActive,
      tasks: [
        ...item.tasks.map(mapStepRecordToFormValue),
        { type: 'text', text: '', delaySeconds: 0 },
      ],
    });
    setTaskModalOpen(true);
    void loadTaskLookups();
  };

  const closeTaskModal = () => {
    setTaskModalOpen(false);
  };

  const cleanupTaskModal = () => {
    setEditingTask(null);
    taskForm.resetFields();
  };

  const saveTask = async () => {
    try {
      const values = await taskForm.validateFields();
      setSubmitting(true);
      const payload: TaskCommandPayload = {
        groupId: values.groupId,
        name: values.name.trim(),
        command: values.command.trim(),
        isActive: values.isActive,
        tasks: values.tasks.map(buildStepPayload),
      };

      if (editingTask) {
        await updateTaskCommand(editingTask.id, payload);
      } else {
        await createTaskCommand(payload);
      }

      closeTaskModal();
      await loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
    } catch {
      // 表单校验和请求错误由 Ant Design 与全局拦截器展示。
    } finally {
      setSubmitting(false);
    }
  };

  const removeTask = async (item: TaskCommandRecord) => {
    try {
      await deleteTaskCommand(item.id);
      await loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
    } catch {
      // 删除错误由全局拦截器展示。
    }
  };

  const confirmRemoveTask = (item: TaskCommandRecord) => {
    Modal.confirm({
      title: '确认删除任务指令？',
      content: `即将删除「${item.name}（${item.command}）」，该指令下的子任务配置也会一并删除。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      centered: true,
      onOk: () => removeTask(item),
    });
  };

  const buildCurrentGroupExport = async (group: CommandGroupRecord): Promise<CommandGroupFullExportPayload> => {
    if (group.groupType === 'control') {
      const commands = await collectPages<ControlCommandRecord>((page) => fetchControlCommands({ page, pageSize: LOOKUP_PAGE_SIZE, groupId: group.id, isActive: 'all' }));
      return {
        format: 'command-group-full-v1',
        exportedAt: new Date().toISOString(),
        group: {
          name: group.name,
          groupType: group.groupType,
          exportEnabled: group.exportEnabled,
          isActive: group.isActive,
        },
        controlCommands: commands,
        taskCommands: [],
      };
    }

    const commands = await collectPages<TaskCommandRecord>((page) => fetchTaskCommands({ page, pageSize: LOOKUP_PAGE_SIZE, groupId: group.id, isActive: 'all' }));
    return {
      format: 'command-group-full-v1',
      exportedAt: new Date().toISOString(),
      group: {
        name: group.name,
        groupType: group.groupType,
        exportEnabled: group.exportEnabled,
        isActive: group.isActive,
      },
      controlCommands: [],
      taskCommands: commands,
    };
  };

  const exportCurrentGroupCommands = async () => {
    if (!selectedGroup) return;
    setTransferLoading(true);
    try {
      const payload = await buildCurrentGroupExport(selectedGroup);
      const safeName = selectedGroup.name.trim().replace(/[\\/:*?"<>|]/g, '_') || 'command-group';
      downloadJson(payload, `command-group-full-${safeName}-${formatTimestamp()}.json`);
      message.success('已导出当前指令管理');
    } catch {
      // 请求错误由全局拦截器展示。
    } finally {
      setTransferLoading(false);
    }
  };

  const resolveImportedStep = (step: TaskCommandRecord['tasks'][number], lookups: TaskLookupCollections): TaskCommandStepPayload => {
    const content = step.content || {};
    const commandCode = String(content.command || '');
    const pointCommand = String(content.command || '');
    const resourceName = String(content.name || '');
    const resourceFileName = String(content.fileName || '');
    const controlCommand = lookups.controlCommands.find((item) => item.command === commandCode);
    const point = lookups.points.find((item) => item.command === pointCommand);
    const resources = step.type === 'image' ? lookups.imageResources : lookups.videoResources;
    const resource = resources.find((item) => item.name === resourceName || (resourceFileName && item.fileName === resourceFileName));

    const payload = buildStepPayload(
      {
        type: step.type,
        delaySeconds: step.delaySeconds,
        waitForInnerTasks: Boolean(step.waitForInnerTasks),
        controlCommandId: step.type === 'command' ? controlCommand?.id ?? null : null,
        pointId: step.type === 'navigation' ? point?.id ?? null : null,
        resourceId: step.type === 'image' || step.type === 'video' ? resource?.id ?? null : null,
        text: step.text || String(content.text || ''),
        imageText: step.imageText || String(content.imageText || ''),
      },
      Number(step.order || 1) - 1,
    );
    if (step.type === 'navigation') {
      payload.innerTasks = (step.innerTasks ?? [])
        .filter((innerStep) => innerStep.type !== 'navigation')
        .map((innerStep) => resolveImportedStep(innerStep, lookups));
    }
    return payload;
  };

  const getImportableTaskSteps = (command: TaskCommandRecord, lookups: TaskLookupCollections) => {
    const missingAssets: ImportMissingAsset[] = [];
    const steps = command.tasks.filter((step) => {
      const content = step.content || {};
      const commandCode = String(content.command || '');
      const resourceName = String(content.name || '');
      const resourceFileName = String(content.fileName || '');
      const resourceLabel = resourceName || resourceFileName || `第 ${step.order} 个子任务`;

      if (step.type === 'command' && !lookups.controlCommands.some((item) => item.command === commandCode)) {
        missingAssets.push({
          commandName: command.name,
          commandCode: command.command,
          stepOrder: step.order,
          assetType: '控制指令',
          assetName: commandCode || resourceLabel,
          action: 'skip-step',
        });
        return false;
      }

      if (step.type === 'navigation' && !lookups.points.some((item) => item.command === commandCode)) {
        missingAssets.push({
          commandName: command.name,
          commandCode: command.command,
          stepOrder: step.order,
          assetType: '点位',
          assetName: commandCode || resourceLabel,
          action: 'skip-step',
        });
        return false;
      }

      if (step.type === 'image' || step.type === 'video') {
        const resources = step.type === 'image' ? lookups.imageResources : lookups.videoResources;
        const matched = resources.some((item) => item.name === resourceName || (resourceFileName && item.fileName === resourceFileName));
        if (!matched) {
          missingAssets.push({
            commandName: command.name,
            commandCode: command.command,
            stepOrder: step.order,
            assetType: step.type === 'image' ? '图片素材' : '视频素材',
            assetName: resourceLabel,
            action: 'skip-step',
          });
          return false;
        }
      }

      return true;
    });

    if (steps.length === 0 && missingAssets.length > 0) {
      missingAssets.forEach((item) => {
        item.action = 'skip-command';
      });
    }

    return { steps, missingAssets };
  };

  const showImportMissingAssets = (missingAssets: ImportMissingAsset[]) => {
    if (missingAssets.length === 0) return;

    Modal.warning({
      title: '部分指令未导入',
      width: 720,
      content: (
        <div className="mt-3 max-h-[420px] overflow-y-auto">
          <Typography.Paragraph className="mb-3 text-slate-600">
            以下子任务引用的素材已不存在，已自动跳过；同一指令内其他子任务会正常导入。
          </Typography.Paragraph>
          <div className="space-y-2">
            {missingAssets.map((item, index) => (
              <div key={`${item.commandCode}-${item.stepOrder}-${item.assetType}-${index}`} className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm">
                <div className="font-semibold text-slate-800">{item.commandName}（{item.commandCode}）</div>
                <div className="mt-1 text-slate-600">
                  第 {item.stepOrder} 个子任务缺少{item.assetType}：{item.assetName}
                  {item.action === 'skip-command' ? '；该指令没有可导入的子任务，已跳过整条指令' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      ),
    });
  };

  const importCurrentGroupCommands = async (file: File) => {
    if (!selectedGroup) return;
    setTransferLoading(true);
    try {
      const payload = JSON.parse(await file.text()) as unknown;
      if (!isCommandGroupFullExportPayload(payload)) {
        message.error('导入文件格式不正确');
        return;
      }
      if (payload.group.groupType !== selectedGroup.groupType) {
        message.error('导入文件类型与当前指令管理类型不一致');
        return;
      }

      const sourceCommands = selectedGroup.groupType === 'control' ? payload.controlCommands : payload.taskCommands;
      const existingCommands = selectedGroup.groupType === 'control'
        ? await collectPages<ControlCommandRecord>((page) => fetchControlCommands({ page, pageSize: LOOKUP_PAGE_SIZE, groupId: selectedGroup.id, isActive: 'all' }))
        : await collectPages<TaskCommandRecord>((page) => fetchTaskCommands({ page, pageSize: LOOKUP_PAGE_SIZE, groupId: selectedGroup.id, isActive: 'all' }));
      const taskLookups = selectedGroup.groupType === 'task' ? await loadTaskLookups() : null;
      if (selectedGroup.groupType === 'task' && !taskLookups) {
        message.error('导入前查找项加载失败，请稍后重试');
        return;
      }
      const currentCodes = new Set(
        selectedGroup.groupType === 'control'
          ? (existingCommands as ControlCommandRecord[]).map((item) => item.command)
          : (existingCommands as TaskCommandRecord[]).map((item) => item.command),
      );
      let created = 0;
      let skipped = 0;
      let failed = 0;
      const missingAssets: ImportMissingAsset[] = [];

      for (const command of sourceCommands) {
        if (currentCodes.has(command.command)) {
          skipped += 1;
          continue;
        }

        try {
          if (selectedGroup.groupType === 'control') {
            const item = command as ControlCommandRecord;
            await createControlCommand({
              groupId: selectedGroup.id,
              name: item.name,
              command: item.command,
              commandValueType: item.commandValueType ?? 'string',
              ip: item.ip,
              port: item.port,
              callMethod: item.callMethod,
              isActive: item.isActive,
            });
          } else {
            const item = command as TaskCommandRecord;
            const { steps, missingAssets: commandMissingAssets } = getImportableTaskSteps(item, taskLookups!);
            if (commandMissingAssets.length > 0) {
              missingAssets.push(...commandMissingAssets);
            }
            if (steps.length === 0) {
              skipped += 1;
              continue;
            }

            await createTaskCommand({
              groupId: selectedGroup.id,
              name: item.name,
              command: item.command,
              isActive: item.isActive,
              tasks: steps.map((step) => resolveImportedStep(step, taskLookups!)),
            });
          }
          currentCodes.add(command.command);
          created += 1;
        } catch {
          failed += 1;
        }
      }

      await loadCommands(selectedGroup, { page: commandPage, keyword: commandKeyword });
      if (selectedGroup.groupType === 'control') {
        invalidateTaskLookupCache();
      }
      message.success(`导入完成：新增 ${created} 条，跳过 ${skipped} 条，失败 ${failed} 条`);
      showImportMissingAssets(missingAssets);
    } catch {
      message.error('导入文件读取失败');
    } finally {
      setTransferLoading(false);
    }
  };

  const controlCommandOptions = useMemo(
    () => controlLookups.map((item) => ({ label: `${item.name} (${item.command})`, value: item.id })),
    [controlLookups],
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

  const canCreateCurrentCommand = selectedGroup?.groupType === 'control' ? canCreateControl : canCreateTask;

  const renderControlCommandCards = () => {
    if (commandsLoading) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="正在加载控制指令" />;
    }

    if (controlCommands.length === 0) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无控制指令" />;
    }

    return (
      <>
        {paginatedControlCommands.map((item) => (
      <article key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Typography.Title level={5} className="mb-0 text-[16px] text-slate-900">
                {item.name}
              </Typography.Title>
              <Tag color="blue">{item.command}</Tag>
              <Tag color={item.isActive ? 'green' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
            </div>
          </div>
          <Space size={8} wrap>
            {canUpdateControl ? <Button size="small" icon={<IconEdit />} onClick={() => openEditControl(item)}>编辑</Button> : null}
            {canDeleteControl ? (
              <Button size="small" danger icon={<IconTrash />} onClick={() => confirmRemoveControl(item)}>删除</Button>
            ) : null}
          </Space>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-4">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-xs text-slate-500">ip</div>
            <div className="mt-1 break-all text-sm text-slate-700">{item.ip || '-'}</div>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-xs text-slate-500">端口</div>
            <div className="mt-1 text-sm text-slate-700">{item.port || '-'}</div>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-xs text-slate-500">调用方式</div>
            <div className="mt-1 text-sm text-slate-700">{item.callMethod}</div>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-xs text-slate-500">指令类型</div>
            <div className="mt-1 text-sm text-slate-700">
              {commandValueTypeLabels[item.commandValueType ?? 'string']}
            </div>
          </div>
        </div>
      </article>
        ))}
        {commandTotal > COMMAND_CARD_PAGE_SIZE ? (
          <div className="flex justify-end pt-1">
            <Pagination
              current={commandPage}
              pageSize={COMMAND_CARD_PAGE_SIZE}
              total={commandTotal}
              showSizeChanger={false}
              onChange={setCommandPage}
            />
          </div>
        ) : null}
      </>
    );
  };

  const renderTaskCommandCards = () => {
    if (commandsLoading) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="正在加载任务指令" />;
    }

    if (taskCommands.length === 0) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务指令" />;
    }

    return (
      <>
        {paginatedTaskCommands.map((item) => (
      <article key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Typography.Title level={5} className="mb-0 text-[16px] text-slate-900">
                {item.name}
              </Typography.Title>
              <Tag color="blue">{item.command}</Tag>
              <Tag color={item.isActive ? 'green' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
            </div>
          </div>
          <Space size={8} wrap>
            {canUpdateTask ? <Button size="small" icon={<IconEdit />} onClick={() => openEditTask(item)}>编辑</Button> : null}
            {canUpdateTask ? <Button size="small" type="primary" icon={<IconPlus />} onClick={() => openAppendTaskStep(item)}>新增子任务</Button> : null}
            {canDeleteTask ? (
              <Button size="small" danger icon={<IconTrash />} onClick={() => confirmRemoveTask(item)}>删除</Button>
            ) : null}
          </Space>
        </div>

        <div className="mt-4 overflow-hidden rounded-lg border border-slate-100">
          <div className="grid grid-cols-[72px_160px_120px_minmax(0,1fr)] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
            <span>顺序</span>
            <span>类型</span>
            <span>延迟</span>
            <span>内容</span>
          </div>
          {item.tasks.length === 0 ? (
            <div className="px-3 py-4 text-sm text-slate-400">暂无子任务</div>
          ) : (
            item.tasks.map((step) => {
              const innerTaskCount = step.type === 'navigation' ? step.innerTasks?.length ?? 0 : 0;
              return (
                <div key={step.id} className="grid grid-cols-[72px_160px_120px_minmax(0,1fr)] border-t border-slate-100 px-3 py-3 text-sm">
                  <span className="text-slate-700">{step.order}</span>
                  <span><Tag color={taskTypeColors[step.type]}>{taskTypeLabels[step.type]}</Tag></span>
                  <span className="text-slate-700">{step.delaySeconds ?? 0} 秒</span>
                  <span className="flex flex-wrap items-center gap-2">
                    <Typography.Text className="text-slate-700">{getStepSummary(step)}</Typography.Text>
                    {innerTaskCount > 0 ? (
                      <Tag color="cyan">包含 {innerTaskCount} 个子子任务</Tag>
                    ) : null}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </article>
        ))}
        {commandTotal > COMMAND_CARD_PAGE_SIZE ? (
          <div className="flex justify-end pt-1">
            <Pagination
              current={commandPage}
              pageSize={COMMAND_CARD_PAGE_SIZE}
              total={commandTotal}
              showSizeChanger={false}
              onChange={setCommandPage}
            />
          </div>
        ) : null}
      </>
    );
  };

  return (
    <div className="-m-2 rounded-xl bg-[#f4f6fb] p-2 lg:-m-4 lg:p-4">
      <div className="grid min-h-[calc(100vh-210px)] grid-cols-1 gap-4 xl:grid-cols-[272px_minmax(0,1fr)]">
        <aside className="rounded-xl border border-slate-200/70 bg-white shadow-card">
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-4">
            <div>
              <Typography.Title level={4} className="mb-1 text-[16px] text-slate-900">子指令管理</Typography.Title>
              <Typography.Text className="text-xs text-slate-500">配置是否导出和类型</Typography.Text>
            </div>
            {canCreateGroup ? <Button type="primary" size="small" icon={<IconPlus />} onClick={openCreateGroup}>新增</Button> : null}
          </div>

          <div className="space-y-3 p-4">
            <Input.Search allowClear placeholder="搜索分组" value={groupKeyword} onChange={(event) => setGroupKeyword(event.target.value)} />
            {filteredGroups.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={groupsLoading ? '正在加载' : '暂无指令管理'} />
            ) : (
              <div className="max-h-[calc(100vh-390px)] overflow-y-auto pr-1 space-y-3">
                {filteredGroups.map((item) => {
                  const active = item.id === selectedGroup?.id;
                  return (
                    <div
                      key={item.id}
                      className={`w-full rounded-xl border text-left transition ${
                        active ? 'border-brand-300 bg-brand-50/70 shadow-sm' : 'border-slate-200 bg-white hover:border-brand-200 hover:bg-slate-50'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedGroupId(item.id);
                          setCommandKeyword('');
                          setCommandPage(1);
                        }}
                        className="block w-full p-3 text-left"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <Typography.Text strong className="text-slate-900">{item.name}</Typography.Text>
                          <Tag color={groupTypeColors[item.groupType]}>{groupTypeLabels[item.groupType]}</Tag>
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-600">
                          <span>是否导出：{item.exportEnabled ? '是' : '否'}</span>
                          <Tag color={item.isActive ? 'green' : 'default'}>{item.isActive ? '启用' : '停用'}</Tag>
                        </div>
                      </button>
                      <div className="flex gap-2 px-3 pb-3">
                        {canUpdateGroup ? (
                          <Button size="small" onClick={(event) => { event.stopPropagation(); openEditGroup(item); }}>编辑</Button>
                        ) : null}
                        {canDeleteGroup ? (
                          <Button
                            size="small"
                            danger
                            onClick={(event) => {
                              event.stopPropagation();
                              confirmRemoveGroup(item);
                            }}
                          >
                            删除
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        <section className="rounded-xl border border-slate-200/70 bg-white shadow-card">
          <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Typography.Title level={4} className="mb-0 text-[17px] text-slate-900">
                  {selectedGroup?.name || '指令列表'}
                </Typography.Title>
                {selectedGroup ? <Tag color={groupTypeColors[selectedGroup.groupType]}>{groupTypeLabels[selectedGroup.groupType]}</Tag> : null}
              </div>
              <Typography.Text className="text-xs text-slate-500">
                类型：{selectedGroup ? groupTypeLabels[selectedGroup.groupType] : '-'}；每个指令基础参数：名称、指令
              </Typography.Text>
            </div>
            <Space wrap>
              <Input.Search
                allowClear
                placeholder="搜索名称 / 指令"
                value={commandKeyword}
                onChange={(event) => {
                  setCommandKeyword(event.target.value);
                  setCommandPage(1);
                }}
                className="w-56"
              />
              <Button icon={<IconReload />} onClick={refreshCurrentGroup}>刷新</Button>
              {selectedGroup && canExportCommands ? (
                <Button icon={<IconDownload />} loading={transferLoading} onClick={() => void exportCurrentGroupCommands()}>导出指令</Button>
              ) : null}
              {selectedGroup && canCreateCurrentCommand ? (
                <Upload
                  accept=".json,application/json"
                  beforeUpload={(file) => {
                    void importCurrentGroupCommands(file);
                    return Upload.LIST_IGNORE;
                  }}
                  showUploadList={false}
                >
                  <Button icon={<IconUpload />} loading={transferLoading}>导入指令</Button>
                </Upload>
              ) : null}
              {selectedGroup?.groupType === 'control' && canCreateCurrentCommand ? (
                <Button type="primary" icon={<IconPlus />} onClick={openCreateControl}>新增指令</Button>
              ) : null}
              {selectedGroup?.groupType === 'task' && canCreateCurrentCommand ? (
                <Button type="primary" icon={<IconPlus />} onClick={openCreateTask}>新增任务指令</Button>
              ) : null}
            </Space>
          </div>

          <div className="space-y-4 p-5">
            {!selectedGroup ? (
              <Empty description="请先新增指令管理分组" />
            ) : selectedGroup.groupType === 'control' ? (
              renderControlCommandCards()
            ) : (
              renderTaskCommandCards()
            )}
          </div>
        </section>
      </div>

      <Modal
        title={editingGroup ? '编辑指令管理' : '新增指令管理'}
        open={groupModalOpen}
        onCancel={closeGroupModal}
        onOk={() => void saveGroup()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        centered
        okText={editingGroup ? '保存' : '创建'}
        cancelText="取消"
        width={640}
      >
        <Form<CommandGroupPayload> form={groupForm} layout="vertical">
          <Form.Item label="指令管理名称" name="name" rules={[{ required: true, message: '请输入指令管理名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="指令类型" name="groupType" rules={[{ required: true, message: '请选择指令类型' }]}>
            <Select options={[{ label: '控制指令', value: 'control' }, { label: '任务指令', value: 'task' }]} />
          </Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="是否允许导出" name="exportEnabled" valuePropName="checked">
              <Switch checkedChildren="允许" unCheckedChildren="禁止" />
            </Form.Item>
            <Form.Item label="是否启用" name="isActive" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      <Modal
        title={editingControl ? '编辑控制指令' : '新增控制指令'}
        open={controlModalOpen}
        onCancel={closeControlModal}
        onOk={() => void saveControl()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        centered
        okText={editingControl ? '保存' : '创建'}
        cancelText="取消"
        width={720}
      >
        <Form<ControlCommandPayload> form={controlForm} layout="vertical">
          <Form.Item name="groupId" hidden><InputNumber /></Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
              <Input />
            </Form.Item>
            <Form.Item label="指令" name="command" rules={[{ required: true, message: '请输入指令' }]}>
              <Input />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_120px_120px_130px]">
            <Form.Item label="IP" name="ip" rules={[{ required: true, message: '请输入 IP' }]}>
              <Input placeholder="192.168.1.10" />
            </Form.Item>
            <Form.Item label="端口" name="port" rules={[{ required: true, message: '请输入端口' }]}>
              <InputNumber min={1} max={65535} precision={0} className="w-full" />
            </Form.Item>
            <Form.Item label="调用方式" name="callMethod" rules={[{ required: true, message: '请选择调用方式' }]}>
              <Select options={callMethodOptions} />
            </Form.Item>
            <Form.Item label="指令类型" name="commandValueType" rules={[{ required: true, message: '请选择指令类型' }]}>
              <Select options={commandValueTypeOptions} />
            </Form.Item>
          </div>
          <Form.Item label="是否启用" name="isActive" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingTask ? '编辑任务指令' : '新增任务指令'}
        open={taskModalOpen}
        onCancel={closeTaskModal}
        afterOpenChange={(open) => {
          if (!open) cleanupTaskModal();
        }}
        onOk={() => void saveTask()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        centered
        okText={editingTask ? '保存' : '创建'}
        cancelText="取消"
        width={960}
        className={taskCommandModalClassName}
        styles={{ body: taskCommandModalBodyStyle }}
      >
        <Form<TaskCommandFormValues> form={taskForm} layout="vertical">
          <Form.Item name="groupId" hidden><InputNumber /></Form.Item>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
              <Input placeholder="例如：欢迎场景任务" />
            </Form.Item>
            <Form.Item label="指令名称" name="command" rules={[{ required: true, message: '请输入指令名称' }]}>
              <Input placeholder="例如：WELCOME_SCENE" />
            </Form.Item>
          </div>
          <Form.Item label="是否启用" name="isActive" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>

          <TaskStepFormList
            lookupLoading={lookupLoading}
            controlCommandOptions={controlCommandOptions}
            pointOptions={pointOptions}
            imageOptions={imageOptions}
            videoOptions={videoOptions}
          />
        </Form>
      </Modal>
    </div>
  );
};

export const CommandManagementPage = CommandWorkspacePage;
