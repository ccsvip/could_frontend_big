import {
  IconTrash,
  IconEdit,
  IconEye,
  IconPlus,
  IconReload,
  IconRobot,
  IconUpload,
} from '@tabler/icons-react';
import {
  Button,
  Card,
  Checkbox,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
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
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createModelAsset,
  deleteModelAsset,
  fetchModelAssets,
  type ModelAssetListQuery,
  type ModelAssetOrientation,
  type ModelAssetPayload,
  type ModelAssetRecord,
  type ModelAssetType,
  type ModelAssetVisibilityFilter,
  updateModelAsset,
} from '../../api/modules/models';
import { useAuthStore } from '../../store/auth';

type ModelQuickFilter =
  | 'all'
  | 'male'
  | 'female'
  | 'horizontal_male'
  | 'horizontal_female'
  | 'vertical_male'
  | 'vertical_female';

type ModelAssetFormValues = {
  name: string;
  modelType: ModelAssetType;
  orientation: ModelAssetOrientation;
  cloudUrl?: string;
  isVisible: boolean;
  thumbnail?: UploadFile[];
  modelFile?: UploadFile[];
  clearThumbnail?: boolean;
  clearModelFile?: boolean;
};

const quickFilterOptions: { label: string; value: ModelQuickFilter }[] = [
  { label: '全部', value: 'all' },
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
  { label: '横屏男', value: 'horizontal_male' },
  { label: '横屏女', value: 'horizontal_female' },
  { label: '竖屏男', value: 'vertical_male' },
  { label: '竖屏女', value: 'vertical_female' },
];

const visibilityOptions = [
  { label: '全部状态', value: 'all' },
  { label: '仅看显示', value: 'visible' },
  { label: '仅看隐藏', value: 'hidden' },
] as const;

const modelTypeOptions = [
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
] as const;

const orientationOptions = [
  { label: '横屏', value: 'horizontal' },
  { label: '竖屏', value: 'vertical' },
] as const;

const quickFilterQueryMap: Record<ModelQuickFilter, Pick<ModelAssetListQuery, 'modelType' | 'orientation'>> = {
  all: {},
  male: { modelType: 'male' },
  female: { modelType: 'female' },
  horizontal_male: { modelType: 'male', orientation: 'horizontal' },
  horizontal_female: { modelType: 'female', orientation: 'horizontal' },
  vertical_male: { modelType: 'male', orientation: 'vertical' },
  vertical_female: { modelType: 'female', orientation: 'vertical' },
};

const modelTypeTagMap = {
  male: { color: 'blue', text: '男' },
  female: { color: 'magenta', text: '女' },
} as const;

const orientationTagMap = {
  horizontal: { color: 'cyan', text: '横屏' },
  vertical: { color: 'purple', text: '竖屏' },
} as const;

const visibilityTagMap = {
  true: { color: 'processing', text: '显示中' },
  false: { color: 'default', text: '已隐藏' },
} as const;

const getUploadFileList = (event: { fileList?: UploadFile[] } | UploadFile[] | undefined) => {
  if (Array.isArray(event)) {
    return event;
  }
  return event?.fileList ?? [];
};

const formatFileSize = (size: number | null) => {
  if (size === null || size <= 0) {
    return '未自动计算';
  }

  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(2)} KB`;
  }
  if (size < 1024 * 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
  }
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

const getTypeTag = (value: unknown) => {
  const tag = modelTypeTagMap[String(value) as keyof typeof modelTypeTagMap];
  return tag ?? { color: 'default', text: '未知' };
};

const getOrientationTag = (value: unknown) => {
  const tag = orientationTagMap[String(value) as keyof typeof orientationTagMap];
  return tag ?? { color: 'default', text: '未知' };
};

const getVisibilityTag = (value: unknown) => {
  const tag = visibilityTagMap[String(value) as keyof typeof visibilityTagMap];
  return tag ?? visibilityTagMap.false;
};

const renderModelAvatar = (
  item: Pick<ModelAssetRecord, 'hasThumbnail' | 'thumbnailUrl' | 'name' | 'orientation'>,
) => {
  const isVertical = item.orientation === 'vertical';
  const frameClassName = isVertical ? 'h-16 w-10' : 'h-10 w-16';

  if (item.hasThumbnail && item.thumbnailUrl) {
    return (
      <div className="flex h-16 w-16 items-center justify-center">
        <img
          src={item.thumbnailUrl}
          alt={item.name}
          className={`${frameClassName} rounded-md border border-brand-200 bg-white object-contain`}
        />
      </div>
    );
  }

  return (
    <div className="flex h-16 w-16 items-center justify-center">
      <div
        className={`${frameClassName} flex items-center justify-center rounded-md border border-slate-200 bg-slate-100 text-slate-500`}
      >
        <IconRobot />
      </div>
    </div>
  );
};

const renderDownloadLink = (item: Pick<ModelAssetRecord, 'effectiveUrl' | 'localUrl' | 'cloudUrl'>) => {
  if (!item.effectiveUrl) {
    return <Typography.Text className="!text-slate-400">暂无可用下载地址</Typography.Text>;
  }

  const linkText = item.localUrl ? '本地地址' : item.cloudUrl ? '云端地址' : '下载地址';
  const helperText = item.localUrl ? '当前优先使用本地地址' : item.cloudUrl ? '当前使用云端地址' : '已配置下载地址';

  return (
    <Space direction="vertical" size={2}>
      <Typography.Link href={item.effectiveUrl} target="_blank" rel="noreferrer">
        {linkText}
      </Typography.Link>
      <Typography.Text className="!text-xs !text-slate-400">{helperText}</Typography.Text>
    </Space>
  );
};

const renderAddressLink = (url: string, linkText: string, emptyText: string) => {
  if (!url) {
    return <Typography.Text className="!text-slate-400">{emptyText}</Typography.Text>;
  }

  return (
    <Typography.Link href={url} target="_blank" rel="noreferrer">
      {linkText}
    </Typography.Link>
  );
};

const renderModelPreviewImage = (
  item: Pick<ModelAssetRecord, 'hasThumbnail' | 'thumbnailUrl' | 'name' | 'orientation'>,
) => {
  const isVertical = item.orientation === 'vertical';
  const previewClassName = isVertical ? 'h-[220px] w-[124px]' : 'h-[124px] w-[220px]';

  if (item.hasThumbnail && item.thumbnailUrl) {
    return (
      <img
        src={item.thumbnailUrl}
        alt={item.name}
        className={`${previewClassName} rounded-xl border border-brand-200 bg-white object-contain`}
      />
    );
  }

  return (
    <div className={`${previewClassName} flex items-center justify-center rounded-xl bg-slate-100 text-slate-500`}>
      <IconRobot className="text-5xl" />
    </div>
  );
};

export const ModelManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('resources.models.create');
  const canUpdate = hasPermission('resources.models.update');
  const canDelete = hasPermission('resources.models.delete');

  const [items, setItems] = useState<ModelAssetRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [quickFilter, setQuickFilter] = useState<ModelQuickFilter>('all');
  const [visibilityFilter, setVisibilityFilter] = useState<ModelAssetVisibilityFilter>('all');
  const [previewItem, setPreviewItem] = useState<ModelAssetRecord | null>(null);
  const [editingItem, setEditingItem] = useState<ModelAssetRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<ModelAssetFormValues>();

  const query = useMemo<ModelAssetListQuery>(
    () => ({
      page,
      keyword,
      visibility: visibilityFilter,
      ...quickFilterQueryMap[quickFilter],
    }),
    [keyword, page, quickFilter, visibilityFilter],
  );

  const loadData = useCallback(
    async (nextQuery: ModelAssetListQuery = query) => {
      setLoading(true);
      try {
        const response = await fetchModelAssets(nextQuery);
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

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({
      modelType: 'male',
      orientation: 'horizontal',
      isVisible: true,
      thumbnail: [],
      modelFile: [],
      clearThumbnail: false,
      clearModelFile: false,
    });
    setFormVisible(true);
  };

  const openEditModal = useCallback(
    (item: ModelAssetRecord) => {
      setEditingItem(item);
      form.setFieldsValue({
        name: item.name,
        modelType: item.modelType,
        orientation: item.orientation,
        cloudUrl: item.cloudUrl,
        isVisible: item.isVisible,
        thumbnail: [],
        modelFile: [],
        clearThumbnail: false,
        clearModelFile: false,
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
    async (item: ModelAssetRecord) => {
      try {
        await deleteModelAsset(item.id);
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
      const payload: ModelAssetPayload = {
        name: values.name,
        modelType: values.modelType,
        orientation: values.orientation,
        cloudUrl: values.cloudUrl?.trim(),
        isVisible: values.isVisible,
        thumbnail: values.thumbnail?.[0]?.originFileObj,
        modelFile: values.modelFile?.[0]?.originFileObj,
        clearThumbnail: values.clearThumbnail,
        clearModelFile: values.clearModelFile,
      };

      if (editingItem) {
        await updateModelAsset(editingItem.id, payload);
      } else {
        await createModelAsset(payload);
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

  const columns: ColumnsType<ModelAssetRecord> = useMemo(
    () => [
      {
        title: '缩略图',
        dataIndex: 'thumbnailUrl',
        key: 'thumbnail',
        width: 96,
        render: (_, item) => renderModelAvatar(item),
      },
      {
        title: '模型名称',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (value: string) => <Typography.Text strong className="!text-slate-900">{value}</Typography.Text>,
      },
      {
        title: '模型类型',
        dataIndex: 'modelType',
        key: 'modelType',
        width: 100,
        render: (value: unknown) => {
          const tag = getTypeTag(value);
          return <Tag color={tag.color}>{tag.text}</Tag>;
        },
      },
      {
        title: '模型方向',
        dataIndex: 'orientation',
        key: 'orientation',
        width: 100,
        render: (value: unknown) => {
          const tag = getOrientationTag(value);
          return <Tag color={tag.color}>{tag.text}</Tag>;
        },
      },
      {
        title: '模型大小',
        dataIndex: 'modelSize',
        key: 'modelSize',
        width: 130,
        render: (value: number | null) => <Typography.Text>{formatFileSize(value)}</Typography.Text>,
      },
      {
        title: '下载地址',
        dataIndex: 'effectiveUrl',
        key: 'effectiveUrl',
        width: 150,
        render: (_, item) => renderDownloadLink(item),
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
            <Button type="text" icon={<IconEye />} onClick={() => setPreviewItem(item)}>
              详情
            </Button>
            {canUpdate ? (
              <Button type="text" icon={<IconEdit />} onClick={() => openEditModal(item)}>
                编辑
              </Button>
            ) : null}
            {canDelete ? (
              <Popconfirm title="确认删除该模型吗？" onConfirm={() => void handleDelete(item)}>
                <Button type="text" danger icon={<IconTrash />}>
                  删除
                </Button>
              </Popconfirm>
            ) : null}
          </Space>
        ),
      },
    ],
    [canDelete, canUpdate, handleDelete, openEditModal],
  );

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <Space size={10} align="center">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-50 to-brand-100/60 text-brand-700">
                  <IconRobot className="text-xl" />
                </div>
                <div>
                  <Typography.Title level={3} className="!mb-1 !text-slate-900">
                    模型管理
                  </Typography.Title>
                  <Typography.Text className="!text-slate-500">
                    统一维护数字人模型文件、模型类型、屏幕方向、云端兜底地址以及前端可见状态，供生产环境下载消费。
                  </Typography.Text>
                </div>
              </Space>
            </div>
            <Space wrap>
              <Input.Search
                allowClear
                placeholder="搜索模型名称 / 地址 / 文件名"
                onSearch={(value) => {
                  setPage(1);
                  setKeyword(value.trim());
                }}
                className="w-full sm:w-80"
              />
              <Select
                value={visibilityFilter}
                options={visibilityOptions as unknown as { label: string; value: string }[]}
                onChange={(value) => {
                  setPage(1);
                  setVisibilityFilter(value as ModelAssetVisibilityFilter);
                }}
                className="!w-36"
              />
              <Button icon={<IconReload />} onClick={() => void loadData()}>
                刷新
              </Button>
              {canCreate ? (
                <Button type="primary" icon={<IconPlus />} onClick={openCreateModal}>
                  新增模型
                </Button>
              ) : null}
            </Space>
          </div>

          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <Typography.Text className="!text-slate-500">
              快速筛选：支持男、女、横屏男、横屏女、竖屏男、竖屏女等组合场景。
            </Typography.Text>
            <Segmented<ModelQuickFilter>
              options={quickFilterOptions}
              value={quickFilter}
              onChange={(value) => {
                setPage(1);
                setQuickFilter(value);
              }}
            />
          </div>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 1260 }}
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
                  keyword || quickFilter !== 'all' || visibilityFilter !== 'all'
                    ? '当前筛选条件下暂无模型数据'
                    : '暂无模型数据，请先新增模型'
                }
              />
            ),
          }}
        />
      </Card>

      <Modal
        title={previewItem?.name || '模型详情'}
        open={!!previewItem}
        footer={null}
        onCancel={() => setPreviewItem(null)}
        width={940}
        centered
        destroyOnHidden
      >
        {previewItem ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
            <div className="flex flex-col items-center justify-start gap-4 rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex h-[220px] w-full items-center justify-center">
                {renderModelPreviewImage(previewItem)}
              </div>
              <Space wrap>
                <Tag color={getTypeTag(previewItem.modelType).color}>{getTypeTag(previewItem.modelType).text}</Tag>
                <Tag color={getOrientationTag(previewItem.orientation).color}>{getOrientationTag(previewItem.orientation).text}</Tag>
                <Tag color={getVisibilityTag(previewItem.isVisible).color}>{getVisibilityTag(previewItem.isVisible).text}</Tag>
              </Space>
            </div>
            <Space direction="vertical" size={16} className="w-full">
              <Descriptions column={1} size="middle" className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <Descriptions.Item label="模型名称">{previewItem.name}</Descriptions.Item>
                <Descriptions.Item label="模型文件">{previewItem.modelFileName || '未上传模型文件'}</Descriptions.Item>
                <Descriptions.Item label="模型大小">{formatFileSize(previewItem.modelSize)}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{previewItem.updated_at}</Descriptions.Item>
              </Descriptions>
              <Card variant="borderless" className="!rounded-xl !border !border-slate-200 !shadow-none">
                <Space direction="vertical" size={12} className="w-full">
                  <div>
                    <Typography.Text className="!text-slate-500">有效下载地址</Typography.Text>
                    <div className="mt-2">{renderAddressLink(previewItem.effectiveUrl, '打开有效下载地址', '暂无可用下载地址')}</div>
                  </div>
                  <div>
                    <Typography.Text className="!text-slate-500">本地地址</Typography.Text>
                    <div className="mt-2">{renderAddressLink(previewItem.localUrl, '打开本地地址', '未生成本地地址')}</div>
                  </div>
                  <div>
                    <Typography.Text className="!text-slate-500">云端地址</Typography.Text>
                    <div className="mt-2">{renderAddressLink(previewItem.cloudUrl, '打开云端地址', '未填写云端地址')}</div>
                  </div>
                </Space>
              </Card>
            </Space>
          </div>
        ) : null}
      </Modal>

      <Modal
        title={editingItem ? '编辑模型' : '新增模型'}
        open={formVisible}
        onCancel={closeFormModal}
        onOk={() => void handleSubmit()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        centered
        okText={editingItem ? '保存' : '创建'}
        cancelText="取消"
        width={720}
      >
        <Form<ModelAssetFormValues> form={form} layout="vertical">
          <Form.Item label="模型名称" name="name" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如：数字人基础模型" />
          </Form.Item>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Form.Item label="模型类型" name="modelType" rules={[{ required: true, message: '请选择模型类型' }]}>
              <Select options={modelTypeOptions as unknown as { label: string; value: string }[]} />
            </Form.Item>
            <Form.Item label="模型方向" name="orientation" rules={[{ required: true, message: '请选择模型方向' }]}>
              <Select options={orientationOptions as unknown as { label: string; value: string }[]} />
            </Form.Item>
          </div>

          <Form.Item label="云端地址" name="cloudUrl" extra="如果未上传本地模型文件，可仅填写完整云端地址创建记录。" rules={[{ type: 'url', message: '请输入合法的完整云端地址' }]}>
            <Input placeholder="例如：https://cdn.example.com/models/avatar-model.bin" />
          </Form.Item>

          <Form.Item
            label="上传模型缩略图"
            name="thumbnail"
            valuePropName="fileList"
            getValueFromEvent={getUploadFileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept="image/*">
              <Button icon={<IconUpload />}>选择图片</Button>
            </Upload>
          </Form.Item>
          {editingItem ? (
            <Space direction="vertical" size={4} className="!mb-4">
              <Typography.Text className="!text-slate-500">
                {editingItem.hasThumbnail ? `当前缩略图：${editingItem.thumbnailName || '已上传缩略图'}` : '当前未上传缩略图，可继续保持空态。'}
              </Typography.Text>
              {editingItem.hasThumbnail ? (
                <Form.Item name="clearThumbnail" valuePropName="checked" noStyle>
                  <Checkbox>保存时删除现有缩略图</Checkbox>
                </Form.Item>
              ) : null}
            </Space>
          ) : null}

          <Form.Item
            label="上传模型文件"
            name="modelFile"
            valuePropName="fileList"
            getValueFromEvent={getUploadFileList}
            extra="模型文件非必传；若上传后，系统会自动计算大小并生成本地完整地址。"
          >
            <Upload beforeUpload={() => false} maxCount={1}>
              <Button icon={<IconUpload />}>选择模型文件</Button>
            </Upload>
          </Form.Item>
          {editingItem ? (
            <Space direction="vertical" size={4} className="!mb-4">
              <Typography.Text className="!text-slate-500">
                {editingItem.hasModelFile ? `当前模型文件：${editingItem.modelFileName || '已上传模型文件'}` : '当前未上传模型文件，可仅保留云端地址。'}
              </Typography.Text>
              {editingItem.localUrl ? (
                <Typography.Text className="!text-slate-500">
                  当前本地地址：{editingItem.localUrl}
                </Typography.Text>
              ) : null}
              {editingItem.hasModelFile ? (
                <Form.Item name="clearModelFile" valuePropName="checked" noStyle>
                  <Checkbox>保存时删除现有本地模型文件</Checkbox>
                </Form.Item>
              ) : null}
            </Space>
          ) : null}

          <Form.Item label="前端可见" name="isVisible" valuePropName="checked">
            <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
