import {
  CustomerServiceOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PictureOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SoundOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Image,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload/interface';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createVoiceTone,
  deleteVoiceTone,
  fetchVoiceTones,
  type VoiceToneListQuery,
  type VoiceTonePayload,
  type VoiceToneRecord,
  type VoiceToneStatusFilter,
  updateVoiceTone,
} from '../../api/modules/voice-tones';
import { useAuthStore } from '../../store/auth';

type VoiceToneFormValues = {
  name: string;
  voiceCode: string;
  asrText?: string;
  isActive: boolean;
  isVisible: boolean;
  icon?: UploadFile[];
  audio?: UploadFile[];
};

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '仅看启用', value: 'active' },
  { label: '仅看停用', value: 'inactive' },
] as const;

const statusTagMap = {
  true: { color: 'success', text: '启用中' },
  false: { color: 'default', text: '已停用' },
} as const;

const visibilityTagMap = {
  true: { color: 'processing', text: '前端可见' },
  false: { color: 'default', text: '前端隐藏' },
} as const;

const getStatusTag = (value: unknown) => {
  const tag = statusTagMap[String(value) as keyof typeof statusTagMap];
  return tag ?? statusTagMap.false;
};

const getVisibilityTag = (value: unknown) => {
  const tag = visibilityTagMap[String(value) as keyof typeof visibilityTagMap];
  return tag ?? visibilityTagMap.false;
};

const getUploadFileList = (event: { fileList?: UploadFile[] } | UploadFile[] | undefined) => {
  if (Array.isArray(event)) {
    return event;
  }
  return event?.fileList ?? [];
};

const renderVoiceToneAvatar = (
  item: Pick<VoiceToneRecord, 'hasIcon' | 'iconUrl' | 'name' | 'hasAudio'>,
  size: number,
) => {
  if (item.hasIcon && item.iconUrl) {
    return (
      <Avatar
        shape="square"
        size={size}
        src={item.iconUrl}
        alt={item.name}
        className="!border !border-teal-200 !bg-white"
      />
    );
  }

  return (
    <Avatar
      shape="square"
      size={size}
      className={item.hasAudio ? '!bg-teal-100 !text-teal-700 !border !border-teal-200' : '!bg-slate-100 !text-slate-500 !border !border-slate-200'}
      icon={item.hasAudio ? <SoundOutlined /> : <PictureOutlined />}
    />
  );
};

export const VoiceToneManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('resources.voice_tones.create');
  const canUpdate = hasPermission('resources.voice_tones.update');
  const canDelete = hasPermission('resources.voice_tones.delete');

  const [items, setItems] = useState<VoiceToneRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<VoiceToneStatusFilter>('all');
  const [previewItem, setPreviewItem] = useState<VoiceToneRecord | null>(null);
  const [editingItem, setEditingItem] = useState<VoiceToneRecord | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<VoiceToneFormValues>();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const query = useMemo<VoiceToneListQuery>(
    () => ({ page, keyword, status: statusFilter }),
    [page, keyword, statusFilter],
  );

  const loadData = useCallback(
    async (nextQuery: VoiceToneListQuery = query) => {
      setLoading(true);
      try {
        const response = await fetchVoiceTones(nextQuery);
        setItems(response.results);
        setTotal(response.count);
      } catch {
        // 错误由拦截器处理
      } finally {
        setLoading(false);
      }
    },
    [query],
  );

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
    };
  }, []);

  const stopCurrentAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.src = '';
      audioRef.current = null;
    }
    setPlayingId(null);
  }, []);

  const togglePlayback = useCallback(
    async (item: VoiceToneRecord) => {
      if (!item.hasAudio || !item.audioUrl) {
        return;
      }

      if (playingId === item.id && audioRef.current) {
        stopCurrentAudio();
        return;
      }

      stopCurrentAudio();

      const audio = new Audio(item.audioUrl);
      audioRef.current = audio;
      setPlayingId(item.id);

      audio.addEventListener('ended', () => {
        if (audioRef.current === audio) {
          audioRef.current = null;
          setPlayingId(null);
        }
      });
      audio.addEventListener('pause', () => {
        if (audioRef.current === audio && audio.currentTime < audio.duration) {
          audioRef.current = null;
          setPlayingId(null);
        }
      });
      audio.addEventListener('error', () => {
        if (audioRef.current === audio) {
          audioRef.current = null;
          setPlayingId(null);
        }
      });

      try {
        await audio.play();
      } catch {
        if (audioRef.current === audio) {
          audioRef.current = null;
          setPlayingId(null);
        }
      }
    },
    [playingId, stopCurrentAudio],
  );

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({
      isActive: true,
      isVisible: true,
      icon: [],
      audio: [],
    });
    setFormVisible(true);
  };

  const openEditModal = useCallback(
    (item: VoiceToneRecord) => {
      setEditingItem(item);
      form.setFieldsValue({
        name: item.name,
        voiceCode: item.voiceCode,
        asrText: item.asrText,
        isActive: item.isActive,
        isVisible: item.isVisible,
        icon: [],
        audio: [],
      });
      setFormVisible(true);
    },
    [form],
  );

  const closeFormModal = () => {
    setFormVisible(false);
    setEditingItem(null);
    form.resetFields();
  };

  const handleDelete = useCallback(
    async (item: VoiceToneRecord) => {
      try {
        await deleteVoiceTone(item.id);
        if (items.length === 1 && page > 1) {
          setPage((current) => current - 1);
        } else {
          void loadData();
        }
      } catch {
        // 错误由拦截器处理
      }
    },
    [items.length, loadData, page],
  );

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: VoiceTonePayload = {
        name: values.name,
        voiceCode: values.voiceCode,
        asrText: values.asrText,
        isActive: values.isActive,
        isVisible: values.isVisible,
        icon: values.icon?.[0]?.originFileObj,
        audio: values.audio?.[0]?.originFileObj,
      };

      if (editingItem) {
        await updateVoiceTone(editingItem.id, payload);
      } else {
        await createVoiceTone(payload);
      }

      closeFormModal();
      if (!editingItem) {
        setPage(1);
      }
      void loadData(editingItem ? query : { ...query, page: 1 });
    } catch {
      // 错误由拦截器处理
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ColumnsType<VoiceToneRecord> = useMemo(
    () => [
      {
        title: '图标',
        dataIndex: 'iconUrl',
        key: 'icon',
        width: 90,
        render: (_, item) => renderVoiceToneAvatar(item, 42),
      },
      {
        title: '音色名称',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (value: string) => <Typography.Text strong className="!text-slate-900">{value}</Typography.Text>,
      },
      {
        title: '音色标识',
        dataIndex: 'voiceCode',
        key: 'voiceCode',
        width: 220,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: 'ASR结果',
        dataIndex: 'asrText',
        key: 'asrText',
        render: (value: string) => (
          <Typography.Paragraph className="!mb-0 !text-slate-500" ellipsis={{ rows: 2 }}>
            {value || '暂无 ASR 结果'}
          </Typography.Paragraph>
        ),
      },
      {
        title: '前端可见',
        dataIndex: 'isVisible',
        key: 'isVisible',
        width: 120,
        render: (value: unknown) => {
          const tag = getVisibilityTag(value);
          return <Tag color={tag.color}>{tag.text}</Tag>;
        },
      },
      {
        title: '试听',
        key: 'audioPreview',
        width: 180,
        render: (_, item) => {
          if (!item.hasAudio || !item.audioUrl) {
            return (
              <Space size={8}>
                <Button type="default" icon={<PlayCircleOutlined />} disabled>
                  播放
                </Button>
                <Typography.Text className="!text-slate-400">未上传音频</Typography.Text>
              </Space>
            );
          }

          const isPlaying = playingId === item.id;
          return (
            <Button
              type={isPlaying ? 'primary' : 'default'}
              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
              onClick={() => void togglePlayback(item)}
            >
              {isPlaying ? '暂停' : '播放'}
            </Button>
          );
        },
      },
      {
        title: '状态',
        dataIndex: 'isActive',
        key: 'isActive',
        width: 110,
        render: (value: unknown) => {
          const tag = getStatusTag(value);
          return <Tag color={tag.color}>{tag.text}</Tag>;
        },
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 180,
      },
      {
        title: '操作',
        key: 'actions',
        width: 210,
        render: (_, item) => (
          <Space size={4}>
            <Button type="text" icon={<EyeOutlined />} onClick={() => setPreviewItem(item)}>
              预览
            </Button>
            {canUpdate ? (
              <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(item)}>
                编辑
              </Button>
            ) : null}
            {canDelete ? (
              <Popconfirm title="确认删除该音色吗？" onConfirm={() => void handleDelete(item)}>
                <Button type="text" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            ) : null}
          </Space>
        ),
      },
    ],
    [canDelete, canUpdate, handleDelete, openEditModal, playingId, togglePlayback],
  );

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <Space size={10} align="center">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-teal-50 to-teal-100/60 text-teal-700">
                <CustomerServiceOutlined className="text-xl" />
              </div>
              <div>
                <Typography.Title level={3} className="!mb-1 !text-slate-900">
                  音色管理
                </Typography.Title>
                <Typography.Text className="!text-slate-500">
                  统一维护音色名称、业务标识、ASR结果、图标图片、音色文件以及前端可见状态，供后续数字人配置与前台展示使用。
                </Typography.Text>
              </div>
            </Space>
          </div>
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索名称 / 音色标识"
              onSearch={(value) => {
                setPage(1);
                setKeyword(value.trim());
              }}
              className="!w-72"
            />
            <Select
              value={statusFilter}
              options={statusOptions as unknown as { label: string; value: string }[]}
              onChange={(value) => {
                setPage(1);
                setStatusFilter(value as VoiceToneStatusFilter);
              }}
              className="!w-36"
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>
              刷新
            </Button>
            {canCreate ? (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建音色
              </Button>
            ) : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            onChange: (nextPage) => setPage(nextPage),
          }}
          locale={{
            emptyText: (
              <Empty
                description={
                  keyword || statusFilter !== 'all'
                    ? '当前筛选条件下暂无音色数据'
                    : '暂无音色数据，请先新建音色'
                }
              />
            ),
          }}
        />
      </Card>

      <Modal
        title={previewItem?.name || '音色详情'}
        open={!!previewItem}
        footer={null}
        onCancel={() => setPreviewItem(null)}
        width={920}
        destroyOnHidden
      >
        {previewItem ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
            <div className={`flex flex-col items-center justify-start gap-4 rounded-xl border p-5 ${previewItem.hasAudio || previewItem.hasIcon ? 'border-teal-200 bg-teal-50/60' : 'border-slate-200 bg-slate-50'}`}>
              {previewItem.hasIcon && previewItem.iconUrl ? (
                <Image
                  src={previewItem.iconUrl}
                  alt={previewItem.name}
                  width={160}
                  height={160}
                  className="rounded-xl object-cover"
                  fallback=""
                  preview={false}
                />
              ) : (
                <div className="flex h-40 w-40 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
                  <SoundOutlined className="text-5xl" />
                </div>
              )}
              <Space wrap>
                <Tag color={getVisibilityTag(previewItem.isVisible).color}>{getVisibilityTag(previewItem.isVisible).text}</Tag>
                <Tag color={getStatusTag(previewItem.isActive).color}>{getStatusTag(previewItem.isActive).text}</Tag>
              </Space>
            </div>
            <Space direction="vertical" size={16} className="w-full">
              <Descriptions column={1} size="middle" className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <Descriptions.Item label="音色名称">{previewItem.name}</Descriptions.Item>
                <Descriptions.Item label="音色标识">
                  <Typography.Text code>{previewItem.voiceCode}</Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="图标文件">{previewItem.iconName || '未上传图标'}</Descriptions.Item>
                <Descriptions.Item label="音色文件">{previewItem.audioName || '未上传音频'}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{previewItem.updated_at}</Descriptions.Item>
              </Descriptions>
              <Card variant="borderless" className="!rounded-xl !border !border-slate-200 !shadow-none">
                <Typography.Text className="!text-slate-500">ASR结果</Typography.Text>
                <Typography.Paragraph className="!mb-0 !mt-3 whitespace-pre-wrap !text-slate-700">
                  {previewItem.asrText || '暂无 ASR 结果'}
                </Typography.Paragraph>
              </Card>
            </Space>
          </div>
        ) : null}
      </Modal>

      <Modal
        title={editingItem ? '编辑音色' : '新建音色'}
        open={formVisible}
        onCancel={closeFormModal}
        onOk={() => void handleSubmit()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        okText={editingItem ? '保存' : '创建'}
        cancelText="取消"
      >
        <Form<VoiceToneFormValues> form={form} layout="vertical">
          <Form.Item label="音色名称" name="name" rules={[{ required: true, message: '请输入音色名称' }]}>
            <Input placeholder="例如：温柔女声" />
          </Form.Item>
          <Form.Item
            label="音色标识"
            name="voiceCode"
            extra="前后端传值统一使用此字段，要求唯一。"
            rules={[{ required: true, message: '请输入音色标识' }]}
          >
            <Input placeholder="例如：voice_female_soft_v1" />
          </Form.Item>
          <Form.Item label="ASR结果" name="asrText">
            <Input.TextArea rows={4} placeholder="请输入该音色对应的 ASR 结果文本" />
          </Form.Item>
          <Form.Item
            label="上传音色图标"
            name="icon"
            valuePropName="fileList"
            getValueFromEvent={getUploadFileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept="image/*">
              <Button icon={<UploadOutlined />}>选择图片</Button>
            </Upload>
          </Form.Item>
          {editingItem ? (
            <Typography.Text className="!text-slate-500">
              {editingItem.hasIcon ? `当前图标：${editingItem.iconName || '已上传图标'}` : '当前未上传图标，可继续保持空态。'}
            </Typography.Text>
          ) : null}
          <Form.Item
            label="上传音色文件"
            name="audio"
            valuePropName="fileList"
            getValueFromEvent={getUploadFileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept="audio/*">
              <Button icon={<UploadOutlined />}>选择音频</Button>
            </Upload>
          </Form.Item>
          {editingItem ? (
            <Typography.Text className="!text-slate-500">
              {editingItem.hasAudio ? `当前音频：${editingItem.audioName || '已上传音频'}` : '当前未上传音频，可继续保持空态。'}
            </Typography.Text>
          ) : null}
          <Form.Item label="前端可见" name="isVisible" valuePropName="checked">
            <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
          </Form.Item>
          <Form.Item label="启用状态" name="isActive" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
