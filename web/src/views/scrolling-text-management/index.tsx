import {
  IconTrash,
  IconEdit,
  IconEye,
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
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  createScrollingText,
  deleteScrollingText,
  fetchScrollingTexts,
  type ScrollingTextItem,
  type ScrollingTextListQuery,
  type ScrollingTextPayload,
  type ScrollingTextRecord,
  type ScrollingTextStatusFilter,
  updateScrollingText,
} from '../../api/modules/scrolling-texts';
import { useAuthStore } from '../../store/auth';

type ScrollingTextFormValues = Pick<ScrollingTextPayload, 'i18nScheme' | 'items'>;

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '仅看启用', value: 'active' },
  { label: '仅看停用', value: 'inactive' },
] as const;

const i18nSchemeOptions = [
  { label: '中英', value: 'zh_en' },
] as const;

const statusTagMap = {
  true: { color: 'success', text: '启用中' },
  false: { color: 'default', text: '已停用' },
} as const;

const normalizeItems = (items: ScrollingTextItem[]) =>
  items.map((item, index) => ({
    ...item,
    order: index + 1,
    zh: item.zh.trim(),
    en: item.en.trim(),
  }));

export const ScrollingTextManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('resources.scrolling_texts.create');
  const canUpdate = hasPermission('resources.scrolling_texts.update');
  const canDelete = hasPermission('resources.scrolling_texts.delete');

  const [items, setItems] = useState<ScrollingTextRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [existingRecordCount, setExistingRecordCount] = useState<number | null>(null);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<ScrollingTextStatusFilter>('all');
  const [previewItem, setPreviewItem] = useState<ScrollingTextRecord | null>(null);
  const [editingItem, setEditingItem] = useState<ScrollingTextRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<ScrollingTextFormValues>();
  const [searchParams] = useSearchParams();
  const titleFilter = searchParams.get('title')?.trim() || '';

  const query = useMemo<ScrollingTextListQuery>(
    () => ({ page: 1, title: titleFilter, keyword, status: statusFilter, lang: 'zh' }),
    [titleFilter, keyword, statusFilter],
  );
  const canOpenCreate = existingRecordCount === null || existingRecordCount === 0;

  const loadData = useCallback(
    async (nextQuery: ScrollingTextListQuery = query) => {
      setLoading(true);
      try {
        const response = await fetchScrollingTexts(nextQuery);
        setItems(response.results);
      } catch {
        // 错误由请求拦截器统一提示。
      } finally {
        setLoading(false);
      }
    },
    [query],
  );

  const refreshRecordLimit = useCallback(async () => {
    try {
      const response = await fetchScrollingTexts({ page: 1, status: 'all', lang: 'zh' });
      setExistingRecordCount(response.count);
    } catch {
      // 错误由请求拦截器统一提示。
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    void refreshRecordLimit();
  }, [refreshRecordLimit]);

  const openCreateModal = () => {
    if (!canOpenCreate) {
      return;
    }
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({
      i18nScheme: 'zh_en',
      items: [{ order: 1, zh: '', en: '' }],
    });
    setFormVisible(true);
  };

  const openEditModal = useCallback(
    (item: ScrollingTextRecord) => {
      setEditingItem(item);
      form.setFieldsValue({
        i18nScheme: item.i18nScheme,
        items: item.items.length > 0 ? item.items : [{ order: 1, zh: '', en: '' }],
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

  const handleDelete = async (item: ScrollingTextRecord) => {
    try {
      await deleteScrollingText(item.id);
      setExistingRecordCount((current) => (current === null ? current : Math.max(current - 1, 0)));
      void refreshRecordLimit();
      void loadData();
    } catch {
      // 错误由请求拦截器统一提示。
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const normalizedItems = normalizeItems(values.items);
      const payload: ScrollingTextPayload = {
        title: editingItem?.title || normalizedItems[0]?.zh || normalizedItems[0]?.en || '滚动文本',
        i18nScheme: values.i18nScheme,
        isActive: editingItem?.isActive ?? true,
        items: normalizedItems,
      };

      if (editingItem) {
        await updateScrollingText(editingItem.id, payload);
      } else {
        await createScrollingText(payload);
        setExistingRecordCount(1);
      }

      closeFormModal();
      void refreshRecordLimit();
      void loadData(query);
    } catch {
      // 表单校验和接口错误均在原处展示。
    } finally {
      setSubmitting(false);
    }
  };

  const columns = useMemo<ColumnsType<ScrollingTextRecord>>(
    () => [
      {
        title: '标题',
        dataIndex: 'title',
        key: 'title',
        render: (value: string, record) => (
          <Space direction="vertical" size={2}>
            <Typography.Text strong className="text-slate-900">
              {value}
            </Typography.Text>
            <Typography.Text className="text-xs text-slate-400">
              更新于 {record.updated_at}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: '国际化方案',
        dataIndex: 'i18nSchemeLabel',
        key: 'i18nSchemeLabel',
        width: 120,
        render: (value: string) => <Tag color="blue">{value}</Tag>,
      },
      {
        title: '状态',
        dataIndex: 'isActive',
        key: 'isActive',
        width: 110,
        render: (value: boolean) => {
          const tag = statusTagMap[String(value) as keyof typeof statusTagMap];
          return <Tag color={tag.color}>{tag.text}</Tag>;
        },
      },
      {
        title: '文本条数',
        dataIndex: 'items',
        key: 'items',
        width: 110,
        render: (value: ScrollingTextItem[]) => `${value.length} 条`,
      },
      {
        title: '中文预览',
        dataIndex: 'localizedItems',
        key: 'localizedItems',
        render: (_, record) => (
          <Typography.Paragraph className="mb-0 text-slate-500" ellipsis={{ rows: 2 }}>
            {record.localizedItems.map((item) => item.text).join(' / ') || '暂无文本'}
          </Typography.Paragraph>
        ),
      },
      {
        title: '操作',
        key: 'actions',
        width: 220,
        render: (_, record) => (
          <Space wrap>
            <Button type="link" icon={<IconEye />} onClick={() => setPreviewItem(record)}>
              查看
            </Button>
            {canUpdate ? (
              <Button type="link" icon={<IconEdit />} onClick={() => openEditModal(record)}>
                编辑
              </Button>
            ) : null}
            {canDelete ? (
              <Popconfirm title="确认删除该滚动文本吗？" onConfirm={() => void handleDelete(record)}>
                <Button type="link" danger icon={<IconTrash />}>
                  删除
                </Button>
              </Popconfirm>
            ) : null}
          </Space>
        ),
      },
    ],
    [canDelete, canUpdate, openEditModal],
  );

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <Typography.Title level={3} className="mb-1 text-slate-900">
              滚动文本管理
            </Typography.Title>
            <Typography.Text className="text-slate-500">
              维护前端滚动展示的中英文文本，启用后可按 zh/en 返回对应语言内容。
            </Typography.Text>
            {titleFilter ? (
              <div className="mt-2">
                <Tag color="geekblue">标题筛选：{titleFilter}</Tag>
              </div>
            ) : null}
          </div>
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索标题或文本"
              onSearch={(value) => {
                setKeyword(value.trim());
              }}
              className="w-60"
            />
            <Select
              value={statusFilter}
              options={statusOptions as unknown as { label: string; value: string }[]}
              onChange={(value) => {
                setStatusFilter(value as ScrollingTextStatusFilter);
              }}
              className="w-36"
            />
            <Button icon={<IconReload />} onClick={() => void loadData()}>
              刷新
            </Button>
            {canCreate ? (
              <Button type="primary" icon={<IconPlus />} onClick={openCreateModal} disabled={!canOpenCreate}>
                新增滚动文本
              </Button>
            ) : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无滚动文本" /> }}
          scroll={{ x: 920 }}
        />
      </Card>

      <Modal
        title={editingItem ? '编辑滚动文本' : '新增滚动文本'}
        open={formVisible}
        onCancel={closeFormModal}
        onOk={() => void handleSubmit()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        width="min(92vw, 56rem)"
        className="scrolling-text-form-modal"
        okText={editingItem ? '保存' : '创建'}
        cancelText="取消"
      >
        <Form<ScrollingTextFormValues> form={form} layout="vertical">
          <Form.Item label="国际化方案" name="i18nScheme" rules={[{ required: true, message: '请选择国际化方案' }]}>
            <Select options={i18nSchemeOptions as unknown as { label: string; value: string }[]} />
          </Form.Item>

          <Form.List name="items">
            {(fields, { add, remove }) => (
              <Space direction="vertical" size={12} className="w-full">
                <div className="flex items-center justify-between">
                  <Typography.Text strong>滚动文本内容</Typography.Text>
                  <Button icon={<IconPlus />} onClick={() => add({ order: fields.length + 1, zh: '', en: '' })}>
                    新增文本
                  </Button>
                </div>
                {fields.map((field, index) => {
                  const { key: fieldKey, name: fieldName } = field;
                  return (
                  <Card
                    key={fieldKey}
                    size="small"
                    className="rounded-lg border border-slate-200"
                    title={
                      <Space>
                        <IconMenu2 className="text-slate-400" />
                        <span>第 {index + 1} 条</span>
                      </Space>
                    }
                    extra={
                      <Space size={4} wrap>
                        {index > 0 ? (
                          <Button type="link" icon={<IconPlus />} onClick={() => add({ order: index + 1, zh: '', en: '' }, index)}>
                            向上插入
                          </Button>
                        ) : null}
                        {fields.length > 1 ? (
                          <Button danger type="link" icon={<IconTrash />} onClick={() => remove(fieldName)}>
                            删除
                          </Button>
                        ) : null}
                      </Space>
                    }
                  >
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <Form.Item
                        label="中文"
                        name={[fieldName, 'zh']}
                        rules={[{ required: true, whitespace: true, message: '请输入中文文本' }]}
                      >
                        <Input.TextArea rows={3} placeholder="请输入中文滚动文本" />
                      </Form.Item>
                      <Form.Item
                        label="英文"
                        name={[fieldName, 'en']}
                        rules={[{ required: true, whitespace: true, message: '请输入英文文本' }]}
                      >
                        <Input.TextArea rows={3} placeholder="请输入英文滚动文本" />
                      </Form.Item>
                    </div>
                  </Card>
                  );
                })}
              </Space>
            )}
          </Form.List>
        </Form>
      </Modal>

      <Modal
        title={previewItem?.title || '滚动文本详情'}
        open={!!previewItem}
        footer={null}
        onCancel={() => setPreviewItem(null)}
        destroyOnHidden
        width={720}
      >
        {previewItem ? (
          <Space direction="vertical" size={12} className="w-full">
            <Space wrap>
              <Tag color="blue">{previewItem.i18nSchemeLabel}</Tag>
              <Tag color={previewItem.isActive ? 'success' : 'default'}>
                {previewItem.isActive ? '启用中' : '已停用'}
              </Tag>
            </Space>
            {previewItem.items.map((item, index) => (
              <Card key={item.id ?? index} size="small" className="rounded-lg border border-slate-200">
                <Space direction="vertical" size={6} className="w-full">
                  <Typography.Text strong>第 {index + 1} 条</Typography.Text>
                  <Typography.Paragraph className="mb-0 text-slate-700">
                    中文：{item.zh}
                  </Typography.Paragraph>
                  <Typography.Paragraph className="mb-0 text-slate-500">
                    英文：{item.en}
                  </Typography.Paragraph>
                </Space>
              </Card>
            ))}
          </Space>
        ) : null}
      </Modal>
    </Space>
  );
};
