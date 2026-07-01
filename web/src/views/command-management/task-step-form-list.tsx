import { IconEdit, IconPhoto, IconGripVertical, IconRowInsertTop, IconPlus, IconVideo } from '@tabler/icons-react';
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Switch, Tag } from 'antd';
import { useEffect, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import type { TaskCommandPayload, TaskCommandStepPayload, TaskCommandStepRecord, TaskStepType } from '../../api/modules/commands';

export const TEXT_TASK_MAX_LENGTH = 5000;
const DRAG_AUTO_SCROLL_EDGE_SIZE = 90;
const DRAG_AUTO_SCROLL_MAX_SPEED = 18;
export const taskCommandModalClassName = 'task-command-modal';
export const taskCommandModalBodyStyle = {
  maxHeight: 'min(760px, calc(100vh - 220px))',
  overflowY: 'auto',
  paddingRight: 14,
} as const;

export type TaskStepFormValue = {
  type?: TaskStepType;
  controlCommandId?: number | null;
  pointId?: number | null;
  resourceId?: number | null;
  text?: string;
  /** 仅 UI 状态：开启后输入/粘贴时自动去除空格（保留换行）。不进入提交 payload。 */
  stripSpaces?: boolean;
  imageText?: string;
  delaySeconds?: number;
  waitForInnerTasks?: boolean;
  isShow?: boolean;
  innerTasks?: TaskStepFormValue[];
};

/** 去除半角空格、全角空格、Tab 等空白字符，但保留换行符（\r、\n）。 */
const stripInlineWhitespace = (value: string) => value.replace(/[^\S\r\n]+/g, '');

export type TaskCommandFormValues = Omit<TaskCommandPayload, 'tasks'> & {
  tasks: TaskStepFormValue[];
};

type SelectOption = {
  label: string;
  value: number;
};

type TaskStepFormListProps = {
  lookupLoading: boolean;
  controlCommandOptions: SelectOption[];
  pointOptions: SelectOption[];
  imageOptions: SelectOption[];
  videoOptions: SelectOption[];
  name?: string | Array<string | number>;
  basePath?: Array<string | number>;
  label?: string;
  itemTitle?: string;
  addButtonText?: string;
  emptyMessage?: string;
  required?: boolean;
  allowNavigation?: boolean;
  nested?: boolean;
};

export const taskTypeOptions: Array<{ label: string; value: TaskStepType }> = [
  { label: '指令', value: 'command' },
  { label: '文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '导航指令', value: 'navigation' },
];

export const taskTypeLabels: Record<TaskStepType, string> = {
  command: '指令',
  text: '文本',
  image: '图片',
  video: '视频',
  navigation: '导航指令',
};

export const taskTypeColors: Record<TaskStepType, string> = {
  command: 'blue',
  text: 'default',
  image: 'magenta',
  video: 'purple',
  navigation: 'green',
};

export const buildStepPayload = (step: TaskStepFormValue, index: number): TaskCommandStepPayload => {
  const type = step.type as TaskStepType;
  const payload: TaskCommandStepPayload = { order: index + 1, type, delaySeconds: Number(step.delaySeconds ?? 0) };

  if (type === 'command') {
    payload.controlCommandId = step.controlCommandId ?? null;
  }
  if (type === 'navigation') {
    payload.pointId = step.pointId ?? null;
    payload.waitForInnerTasks = Boolean(step.waitForInnerTasks);
    payload.isShow = step.isShow === undefined ? true : Boolean(step.isShow);
    payload.innerTasks = (step.innerTasks ?? []).map(buildStepPayload);
  }
  if (type === 'image' || type === 'video') {
    payload.resourceId = step.resourceId ?? null;
  }
  if (type === 'image') {
    payload.imageText = step.imageText?.trim() || '';
  }
  if (type === 'text') {
    payload.text = step.text?.trim() || '';
  }

  return payload;
};

export const mapStepRecordToFormValue = (step: TaskCommandStepRecord): TaskStepFormValue => ({
  type: step.type,
  controlCommandId: step.controlCommandId ?? null,
  pointId: step.pointId ?? null,
  resourceId: step.resourceId ?? null,
  text: step.text || String(step.content?.text || ''),
  imageText: step.imageText || String(step.content?.imageText || ''),
  delaySeconds: step.delaySeconds ?? 0,
  waitForInnerTasks: Boolean(step.waitForInnerTasks),
  isShow: step.isShow === undefined ? true : Boolean(step.isShow),
  innerTasks: (step.innerTasks ?? []).map(mapStepRecordToFormValue),
});

type DropPosition = 'before' | 'after';

const getDragScrollContainer = (element: HTMLElement): HTMLElement => {
  let current = element.parentElement;

  while (current) {
    const style = window.getComputedStyle(current);
    const canScrollY = current.scrollHeight > current.clientHeight;
    const allowsScrollY = /(auto|scroll|overlay)/.test(style.overflowY);
    if (canScrollY && allowsScrollY) {
      return current;
    }
    current = current.parentElement;
  }

  return document.scrollingElement instanceof HTMLElement ? document.scrollingElement : document.documentElement;
};

export const TaskStepFormList = ({
  lookupLoading,
  controlCommandOptions,
  pointOptions,
  imageOptions,
  videoOptions,
  name = 'tasks',
  basePath = ['tasks'],
  label = '子任务列表',
  itemTitle = '子任务',
  addButtonText = '新增子任务',
  emptyMessage = '请至少配置一个子任务',
  required = true,
  allowNavigation = true,
  nested = false,
}: TaskStepFormListProps) => {
  const form = Form.useFormInstance();
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<{ index: number; position: DropPosition } | null>(null);
  const [innerTaskModalKey, setInnerTaskModalKey] = useState<number | null>(null);
  const autoScrollFrameRef = useRef<number | null>(null);
  const autoScrollContainerRef = useRef<HTMLElement | null>(null);
  const dragClientYRef = useRef<number | null>(null);

  const stopDragAutoScroll = () => {
    if (autoScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(autoScrollFrameRef.current);
      autoScrollFrameRef.current = null;
    }
    autoScrollContainerRef.current = null;
    dragClientYRef.current = null;
  };

  const runDragAutoScroll = () => {
    const container = autoScrollContainerRef.current;
    const clientY = dragClientYRef.current;

    if (!container || clientY === null) {
      autoScrollFrameRef.current = null;
      return;
    }

    const isDocumentContainer = container === document.documentElement || container === document.scrollingElement;
    const rect = isDocumentContainer
      ? { top: 0, bottom: window.innerHeight }
      : container.getBoundingClientRect();
    const distanceToTop = clientY - rect.top;
    const distanceToBottom = rect.bottom - clientY;
    let scrollDelta = 0;

    if (distanceToTop < DRAG_AUTO_SCROLL_EDGE_SIZE) {
      const ratio = (DRAG_AUTO_SCROLL_EDGE_SIZE - Math.max(distanceToTop, 0)) / DRAG_AUTO_SCROLL_EDGE_SIZE;
      scrollDelta = -Math.max(4, Math.round(ratio * DRAG_AUTO_SCROLL_MAX_SPEED));
    } else if (distanceToBottom < DRAG_AUTO_SCROLL_EDGE_SIZE) {
      const ratio = (DRAG_AUTO_SCROLL_EDGE_SIZE - Math.max(distanceToBottom, 0)) / DRAG_AUTO_SCROLL_EDGE_SIZE;
      scrollDelta = Math.max(4, Math.round(ratio * DRAG_AUTO_SCROLL_MAX_SPEED));
    }

    if (scrollDelta !== 0) {
      container.scrollTop += scrollDelta;
      autoScrollFrameRef.current = window.requestAnimationFrame(runDragAutoScroll);
      return;
    }

    autoScrollFrameRef.current = null;
  };

  const updateDragAutoScroll = (event: DragEvent<HTMLElement>) => {
    autoScrollContainerRef.current = getDragScrollContainer(event.currentTarget);
    dragClientYRef.current = event.clientY;
    if (autoScrollFrameRef.current === null) {
      autoScrollFrameRef.current = window.requestAnimationFrame(runDragAutoScroll);
    }
  };

  useEffect(() => stopDragAutoScroll, []);

  const clearDragState = () => {
    setDraggingIndex(null);
    setDropTarget(null);
    stopDragAutoScroll();
  };

  const currentTaskTypeOptions = allowNavigation
    ? taskTypeOptions
    : taskTypeOptions.filter((option) => option.value !== 'navigation');

  const getFieldPath = (fieldName: number, fieldKeyName: string) => [...basePath, fieldName, fieldKeyName];

  const clearNavigationExtras = (fieldName: number) => {
    form.setFieldValue(getFieldPath(fieldName, 'innerTasks'), []);
    form.setFieldValue(getFieldPath(fieldName, 'waitForInnerTasks'), false);
    form.setFieldValue(getFieldPath(fieldName, 'isShow'), true);
  };

  const ensureNavigationDefaults = (fieldName: number) => {
    const currentIsShow = form.getFieldValue(getFieldPath(fieldName, 'isShow'));
    if (currentIsShow === undefined) {
      form.setFieldValue(getFieldPath(fieldName, 'isShow'), true);
    }
  };

  return (
    <Form.List
      name={name}
      rules={required ? [{ validator: async (_, value) => { if (!value || value.length < 1) throw new Error(emptyMessage); } }] : undefined}
    >
      {(fields, { add, remove, move }, { errors }) => (
        <Form.Item label={label} required={required}>
          <Space direction="vertical" className="w-full" size={12}>
            {fields.map((field, index) => {
              const { key: fieldKey, ...fieldProps } = field;
              const isDragging = draggingIndex === index;
              const dropPosition = dropTarget?.index === index && draggingIndex !== null && draggingIndex !== index
                ? dropTarget.position
                : null;

              return (
                <Card
                  key={fieldKey}
                  size="small"
                  draggable
                  onDragStart={(event) => {
                    if (nested) event.stopPropagation();
                    const target = event.target as HTMLElement;
                    // 输入控件内部要保留原生编辑/选中文本体验，拖拽从卡片标题或空白区域开始。
                    if (target.closest('input, textarea, button, .ant-select, .ant-input-number, .ant-card-extra')) {
                      event.preventDefault();
                      return;
                    }
                    setDraggingIndex(index);
                    event.dataTransfer.effectAllowed = 'move';
                    event.dataTransfer.setData('text/plain', String(index));
                  }}
                  onDragOver={(event) => {
                    if (nested) event.stopPropagation();
                    event.preventDefault();
                    event.dataTransfer.dropEffect = 'move';
                    updateDragAutoScroll(event);
                    const rect = event.currentTarget.getBoundingClientRect();
                    const position: DropPosition = event.clientY < rect.top + rect.height / 2 ? 'before' : 'after';
                    setDropTarget({ index, position });
                  }}
                  onDragLeave={(event) => {
                    if (nested) event.stopPropagation();
                    setDropTarget((current) => (current?.index === index ? null : current));
                  }}
                  onDrop={(event) => {
                    if (nested) event.stopPropagation();
                    event.preventDefault();
                    const sourceIndex = Number(event.dataTransfer.getData('text/plain'));
                    if (Number.isInteger(sourceIndex)) {
                      const rawTargetIndex = (dropTarget?.index ?? index) + (dropTarget?.position === 'after' ? 1 : 0);
                      const targetIndex = Math.max(
                        0,
                        Math.min(fields.length - 1, sourceIndex < rawTargetIndex ? rawTargetIndex - 1 : rawTargetIndex),
                      );
                      if (sourceIndex !== targetIndex) {
                        move(sourceIndex, targetIndex);
                      }
                    }
                    clearDragState();
                  }}
                  onDragEnd={(event) => {
                    if (nested) event.stopPropagation();
                    clearDragState();
                  }}
                  className={[
                    '!rounded-lg !border-slate-200 task-step-card--interactive',
                    isDragging ? 'task-step-card--dragging' : '',
                    dropPosition ? 'task-step-card--drop-target' : '',
                    dropPosition === 'before' ? 'task-step-card--drop-before' : '',
                    dropPosition === 'after' ? 'task-step-card--drop-after' : '',
                  ].filter(Boolean).join(' ')}
                  title={(
                    <span className="inline-flex items-center gap-2">
                      <IconGripVertical className="task-step-drag-handle cursor-grab text-slate-400 active:cursor-grabbing" />
                      第 {index + 1} 个{itemTitle}
                    </span>
                  )}
                  extra={(
                    <Space size={6} wrap>
                      {index > 0 ? (
                        <Button
                          size="small"
                          icon={<IconRowInsertTop />}
                          onClick={() => add({ type: 'text', text: '', delaySeconds: 0 }, index)}
                        >
                          向上插入
                        </Button>
                      ) : null}
                      <Button size="small" disabled={index === 0} onClick={() => move(index, index - 1)}>上移</Button>
                      <Button size="small" disabled={index === fields.length - 1} onClick={() => move(index, index + 1)}>下移</Button>
                      <Button size="small" danger disabled={required && fields.length === 1} onClick={() => remove(field.name)}>删除</Button>
                    </Space>
                  )}
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-[180px_160px_190px_1fr]">
                    <Form.Item
                      {...fieldProps}
                      label="子任务类型"
                      name={[field.name, 'type']}
                      rules={[{ required: true, message: '请选择子任务类型' }]}
                    >
                      <Select
                        options={currentTaskTypeOptions}
                        onChange={(value) => {
                          if (value === 'navigation') {
                            ensureNavigationDefaults(field.name);
                          } else {
                            clearNavigationExtras(field.name);
                          }
                        }}
                      />
                    </Form.Item>
                    <Form.Item
                      {...fieldProps}
                      label="延迟时间（秒）"
                      name={[field.name, 'delaySeconds']}
                      rules={[{ required: true, message: '请输入延迟时间' }]}
                    >
                      <InputNumber min={0} precision={0} className="!w-full" suffix="秒" />
                    </Form.Item>
                    <Form.Item shouldUpdate noStyle>
                      {({ getFieldValue }) => {
                        const type = getFieldValue(getFieldPath(field.name, 'type')) as TaskStepType | undefined;
                        if (type !== 'navigation') {
                          return <div className="hidden md:block" />;
                        }
                        return (
                          <Space direction="vertical" size={4} className="w-full">
                            <Form.Item
                              {...fieldProps}
                              label="等待子子任务完成"
                              name={[field.name, 'waitForInnerTasks']}
                              valuePropName="checked"
                              className="!mb-0"
                            >
                              <Switch checkedChildren="等待" unCheckedChildren="不等" />
                            </Form.Item>
                            <Form.Item
                              {...fieldProps}
                              label="是否显示到前端"
                              name={[field.name, 'isShow']}
                              valuePropName="checked"
                              className="!mb-0"
                            >
                              <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
                            </Form.Item>
                          </Space>
                        );
                      }}
                    </Form.Item>
                    <Form.Item shouldUpdate noStyle>
                      {({ getFieldValue }) => {
                        const type = getFieldValue(getFieldPath(field.name, 'type')) as TaskStepType | undefined;
                        if (type === 'command') {
                          return (
                            <Form.Item {...fieldProps} label="选择指令" name={[field.name, 'controlCommandId']} rules={[{ required: true, message: '请选择指令' }]}>
                              <Select showSearch optionFilterProp="label" loading={lookupLoading} options={controlCommandOptions} placeholder="从指令管理中选择控制指令" />
                            </Form.Item>
                          );
                        }
                        if (type === 'text') {
                          const stripSpaces = Boolean(getFieldValue(getFieldPath(field.name, 'stripSpaces')));
                          return (
                            <Space direction="vertical" className="w-full" size={12}>
                              <Form.Item
                                {...fieldProps}
                                label="文本内容"
                                name={[field.name, 'text']}
                                rules={[
                                  { required: true, message: '请输入文本内容' },
                                  { max: TEXT_TASK_MAX_LENGTH, message: `文本内容不能超过 ${TEXT_TASK_MAX_LENGTH} 个字` },
                                ]}
                                getValueFromEvent={(event: { target: { value: string } }) => {
                                  const value = event?.target?.value ?? '';
                                  return stripSpaces ? stripInlineWhitespace(value) : value;
                                }}
                              >
                                <Input.TextArea
                                  rows={4}
                                  maxLength={TEXT_TASK_MAX_LENGTH}
                                  showCount
                                  placeholder={`最多可输入 ${TEXT_TASK_MAX_LENGTH} 个字`}
                                />
                              </Form.Item>
                              <Form.Item
                                {...fieldProps}
                                label="自动去除空格"
                                name={[field.name, 'stripSpaces']}
                                valuePropName="checked"
                                tooltip="开启后输入或粘贴文本时会自动去除半角空格、全角空格与 Tab（保留换行）。"
                              >
                                <Switch
                                  checkedChildren="开"
                                  unCheckedChildren="关"
                                  onChange={(checked) => {
                                    if (!checked) return;
                                    const currentText = getFieldValue(getFieldPath(field.name, 'text')) as string | undefined;
                                    if (typeof currentText === 'string' && currentText.length > 0) {
                                      const stripped = stripInlineWhitespace(currentText);
                                      if (stripped !== currentText) {
                                        form.setFieldValue(getFieldPath(field.name, 'text'), stripped);
                                      }
                                    }
                                  }}
                                />
                              </Form.Item>
                            </Space>
                          );
                        }
                        if (type === 'image') {
                          return (
                            <Space direction="vertical" className="w-full" size={0}>
                              <Form.Item {...fieldProps} label="选择图片" name={[field.name, 'resourceId']} rules={[{ required: true, message: '请选择图片资源' }]}>
                                <Select showSearch optionFilterProp="label" loading={lookupLoading} options={imageOptions} placeholder="从图片资源中选择内容" suffixIcon={<IconPhoto />} />
                              </Form.Item>
                              <Form.Item {...fieldProps} label="图片文本（可选）" name={[field.name, 'imageText']}>
                                <Input placeholder="可不填写，运行时返回空字符串" allowClear />
                              </Form.Item>
                            </Space>
                          );
                        }
                        if (type === 'video') {
                          return (
                            <Form.Item {...fieldProps} label="选择视频" name={[field.name, 'resourceId']} rules={[{ required: true, message: '请选择视频资源' }]}>
                              <Select showSearch optionFilterProp="label" loading={lookupLoading} options={videoOptions} placeholder="从视频资源中选择内容" suffixIcon={<IconVideo />} />
                            </Form.Item>
                          );
                        }
                        if (type === 'navigation') {
                          const innerTasks = getFieldValue(getFieldPath(field.name, 'innerTasks')) as TaskStepFormValue[] | undefined;
                          const innerTaskCount = Array.isArray(innerTasks) ? innerTasks.length : 0;
                          return (
                            <Space direction="vertical" className="w-full" size={12}>
                              <Form.Item {...fieldProps} label="选择导航点位" name={[field.name, 'pointId']} rules={[{ required: true, message: '请选择点位' }]}>
                                <Select showSearch optionFilterProp="label" loading={lookupLoading} options={pointOptions} placeholder="从点位管理中选择内容" />
                              </Form.Item>
                              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                                <Button
                                  icon={<IconEdit />}
                                  onClick={() => setInnerTaskModalKey(fieldKey)}
                                >
                                  配置子子任务
                                </Button>
                                <Tag color={innerTaskCount > 0 ? 'green' : 'default'}>{innerTaskCount} 个子子任务</Tag>
                              </div>
                              <Modal
                                title={`第 ${index + 1} 个子任务的子子任务`}
                                open={innerTaskModalKey === fieldKey}
                                onCancel={() => setInnerTaskModalKey(null)}
                                footer={<Button type="primary" onClick={() => setInnerTaskModalKey(null)}>完成</Button>}
                                width={900}
                                centered
                                destroyOnHidden
                                className={taskCommandModalClassName}
                                styles={{ body: taskCommandModalBodyStyle }}
                              >
                                <TaskStepFormList
                                  lookupLoading={lookupLoading}
                                  controlCommandOptions={controlCommandOptions}
                                  pointOptions={pointOptions}
                                  imageOptions={imageOptions}
                                  videoOptions={videoOptions}
                                  name={[field.name, 'innerTasks']}
                                  basePath={[...basePath, field.name, 'innerTasks']}
                                  label="子子任务列表"
                                  itemTitle="子子任务"
                                  addButtonText="新增子子任务"
                                  emptyMessage="请至少配置一个子子任务"
                                  required={false}
                                  allowNavigation={false}
                                  nested
                                />
                              </Modal>
                            </Space>
                          );
                        }
                        return <div className="pt-8 text-slate-400">请先选择子任务类型</div>;
                      }}
                    </Form.Item>
                  </div>
                </Card>
              );
            })}
            <Button type="dashed" icon={<IconPlus />} onClick={() => add({ type: 'text', text: '', delaySeconds: 0 })} block>{addButtonText}</Button>
            <Form.ErrorList errors={errors} />
          </Space>
        </Form.Item>
      )}
    </Form.List>
  );
};
