import type { Key } from 'react';
import {
  ArrowLeftOutlined,
  BookOutlined,
  BranchesOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FileAddOutlined,
  FileSearchOutlined,
  InboxOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  EditOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  KNOWLEDGE_BASE_ACCEPT,
  bulkDownloadKnowledgeDocuments,
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  fetchKnowledgeBaseDocuments,
  fetchKnowledgeBases,
  indexKnowledgeBase,
  indexKnowledgeDocument,
  recallTestKnowledgeBase,
  updateKnowledgeBase,
  uploadKnowledgeBaseDocument,
  type KnowledgeBaseListQuery,
  type KnowledgeBaseRecord,
  type KnowledgeDocumentListQuery,
  type KnowledgeDocumentRecord,
  type KnowledgeRecallChunk,
} from '../../api/modules/knowledge-base';
import { useAuthStore } from '../../store/auth';

type UploadTaskStatus = 'pending' | 'uploading' | 'success' | 'error';

type UploadTask = {
  id: string;
  file: File;
  progress: number;
  status: UploadTaskStatus;
  error?: string;
};

type KnowledgeBaseFormValues = {
  name: string;
  description?: string;
};

type RecallHistoryItem = {
  id: string;
  query: string;
  mode: string;
  count: number;
};

const PAGE_SIZE = 10;
const MAX_UPLOAD_CONCURRENCY = 3;

const knowledgeBaseHighlights = [
  { label: '资料集中沉淀', description: '将售后政策、产品手册、FAQ 等文档按场景归档，避免智能体直接面对零散文件。' },
  { label: '上传即入库', description: '支持 DOC、PDF、Markdown、Excel 等常见格式，批量上传时自动排队处理。' },
  { label: '召回先验证', description: '上线给智能体前，先用业务问题测试命中的文档片段和相似度。' },
];

const createGuideCards = [
  {
    title: '创建业务知识库',
    description: '按业务域、产品线或部门拆分知识库，方便权限隔离和后续维护。',
    icon: <BookOutlined />,
  },
  {
    title: '上传并维护文档',
    description: `当前支持 ${KNOWLEDGE_BASE_ACCEPT.replace(/\./g, '').toUpperCase()}，建议文件名保留版本和适用范围。`,
    icon: <FileAddOutlined />,
  },
  {
    title: '测试召回效果',
    description: '用真实用户问题检查命中内容，再把知识库绑定到智能体应用。',
    icon: <ExperimentOutlined />,
  },
];

const detailWorkflow = [
  { title: '上传资料', description: '拖入或选择文档，最多 3 个文件并发上传。' },
  { title: '等待处理', description: '后台完成解析、切分和索引后即可参与召回。' },
  { title: '验证命中', description: '用典型问题测试 Top N 片段，确认答案来源可靠。' },
];

const retrievalPolicies = [
  { title: '高质量索引', description: '上传后走解析、切分、Embedding 入库，召回时优先按向量相似度排序。' },
  { title: '关键词降级', description: 'Embedding 模型不可用时自动退回关键词匹配，保证知识库仍可用。' },
  { title: 'Rerank 精排', description: '配置 Rerank 模型后，对 Top N 候选片段二次排序，提升答案来源可信度。' },
];

const indexStatusColor: Record<KnowledgeDocumentRecord['indexingStatus'], string> = {
  pending: 'default',
  indexing: 'processing',
  ready: 'success',
  failed: 'error',
};

const formatFileSize = (value: number | null) => {
  if (value === null || value === undefined) return '--';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};

export const KnowledgeBasePage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canUpload = hasPermission('knowledge_base.upload');
  const canDownload = hasPermission('knowledge_base.download');
  const canBulkDownload = hasPermission('knowledge_base.bulk_download');
  const canDelete = canUpload;

  const [bases, setBases] = useState<KnowledgeBaseRecord[]>([]);
  const [basePage, setBasePage] = useState(1);
  const [baseTotal, setBaseTotal] = useState(0);
  const [baseKeyword, setBaseKeyword] = useState('');
  const [baseLoading, setBaseLoading] = useState(false);
  const [selectedBase, setSelectedBase] = useState<KnowledgeBaseRecord | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createForm] = Form.useForm<KnowledgeBaseFormValues>();
  const [editOpen, setEditOpen] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editingBase, setEditingBase] = useState<KnowledgeBaseRecord | null>(null);
  const [editForm] = Form.useForm<KnowledgeBaseFormValues>();

  const [documents, setDocuments] = useState<KnowledgeDocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentKeyword, setDocumentKeyword] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [downloadLoadingId, setDownloadLoadingId] = useState<number | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null);
  const [deletingBaseId, setDeletingBaseId] = useState<number | null>(null);
  const [indexingDocumentId, setIndexingDocumentId] = useState<number | null>(null);
  const [indexingBase, setIndexingBase] = useState(false);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const uploadTasksRef = useRef<UploadTask[]>([]);

  const [recallQuery, setRecallQuery] = useState('');
  const [recallTopN, setRecallTopN] = useState(5);
  const [recallLoading, setRecallLoading] = useState(false);
  const [recallChunks, setRecallChunks] = useState<KnowledgeRecallChunk[]>([]);
  const [recallMode, setRecallMode] = useState('');
  const [recallHistory, setRecallHistory] = useState<RecallHistoryItem[]>([]);

  useEffect(() => {
    uploadTasksRef.current = uploadTasks;
  }, [uploadTasks]);

  const baseQuery = useMemo<KnowledgeBaseListQuery>(() => ({
    page: basePage,
    keyword: baseKeyword,
  }), [baseKeyword, basePage]);

  const documentQuery = useMemo<KnowledgeDocumentListQuery>(() => ({
    keyword: documentKeyword,
  }), [documentKeyword]);

  const loadBases = useCallback(async (nextQuery: KnowledgeBaseListQuery = baseQuery) => {
    setBaseLoading(true);
    try {
      const response = await fetchKnowledgeBases(nextQuery);
      setBases(response.results);
      setBaseTotal(response.count);
      setSelectedBase((current) => {
        if (!current) return current;
        return response.results.find((item) => item.id === current.id) ?? current;
      });
    } finally {
      setBaseLoading(false);
    }
  }, [baseQuery]);

  const loadDocuments = useCallback(async (nextQuery: KnowledgeDocumentListQuery = documentQuery) => {
    if (!selectedBase) {
      setDocuments([]);
      return;
    }
    setDocumentsLoading(true);
    try {
      const response = await fetchKnowledgeBaseDocuments(selectedBase.id, nextQuery);
      setDocuments(response);
    } finally {
      setDocumentsLoading(false);
    }
  }, [documentQuery, selectedBase]);

  useEffect(() => {
    void loadBases();
  }, [loadBases]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const handleCreateBase = async () => {
    const values = await createForm.validateFields();
    setCreateSaving(true);
    try {
      const created = await createKnowledgeBase({
        name: values.name.trim(),
        description: values.description?.trim(),
      });
      message.success('知识库已创建');
      setCreateOpen(false);
      createForm.resetFields();
      setBasePage(1);
      await loadBases({ page: 1, keyword: baseKeyword });
      setSelectedBase(created);
    } finally {
      setCreateSaving(false);
    }
  };

  const startUpload = useCallback(async (taskId: string) => {
    if (!selectedBase) return;
    const task = uploadTasksRef.current.find((item) => item.id === taskId);
    if (!task) return;

    setUploadTasks((current) => current.map((item) => (
      item.id === taskId ? { ...item, status: 'uploading', progress: 0, error: undefined } : item
    )));

    try {
      await uploadKnowledgeBaseDocument(
        selectedBase.id,
        { file: task.file },
        {
          timeoutMs: 120000,
          onUploadProgress: (percent) => {
            setUploadTasks((current) => current.map((item) => (
              item.id === taskId ? { ...item, progress: percent } : item
            )));
          },
        },
      );
      setUploadTasks((current) => current.map((item) => (
        item.id === taskId ? { ...item, status: 'success', progress: 100 } : item
      )));
      message.success('文档已上传');
      void loadDocuments();
      void loadBases();
    } catch (error) {
      const nextError = error instanceof Error ? error.message : '上传失败';
      setUploadTasks((current) => current.map((item) => (
        item.id === taskId ? { ...item, status: 'error', error: nextError } : item
      )));
    }
  }, [loadBases, loadDocuments, selectedBase]);

  useEffect(() => {
    const uploadingCount = uploadTasks.filter((item) => item.status === 'uploading').length;
    if (uploadingCount >= MAX_UPLOAD_CONCURRENCY) return;
    uploadTasks
      .filter((item) => item.status === 'pending')
      .slice(0, MAX_UPLOAD_CONCURRENCY - uploadingCount)
      .forEach((task) => {
        void startUpload(task.id);
      });
  }, [startUpload, uploadTasks]);

  const enqueueFiles = (files: File[]) => {
    if (!selectedBase || files.length === 0) return;
    setUploadTasks((current) => [
      ...current,
      ...files.map((file) => ({
        id: `${selectedBase.id}-${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        progress: 0,
        status: 'pending' as const,
      })),
    ]);
  };

  const hasInFlightUpload = uploadTasks.some((item) => item.status === 'pending' || item.status === 'uploading');
  const activeBaseCount = bases.filter((item) => item.isActive).length;
  const visibleDocumentCount = bases.reduce((total, item) => total + item.documentCount, 0);
  const latestUpdatedAt = bases.reduce<string | null>((latest, item) => {
    if (!latest) return item.updated_at;
    return item.updated_at > latest ? item.updated_at : latest;
  }, null);

  const openEditBase = useCallback((item: KnowledgeBaseRecord) => {
    setEditingBase(item);
    editForm.setFieldsValue({ name: item.name, description: item.description });
    setEditOpen(true);
  }, [editForm]);

  const handleEditBase = async () => {
    if (!editingBase) return;
    const values = await editForm.validateFields();
    setEditSaving(true);
    try {
      const updated = await updateKnowledgeBase(editingBase.id, {
        name: values.name.trim(),
        description: values.description?.trim() || '',
      });
      message.success('知识库已更新');
      setEditOpen(false);
      setEditingBase(null);
      setSelectedBase((current) => (current?.id === updated.id ? updated : current));
      await loadBases();
    } finally {
      setEditSaving(false);
    }
  };

  const handleSingleDownload = useCallback(async (item: KnowledgeDocumentRecord) => {
    setDownloadLoadingId(item.id);
    try {
      await downloadKnowledgeDocument(item);
      void loadDocuments();
    } finally {
      setDownloadLoadingId(null);
    }
  }, [loadDocuments]);

  const handleBulkDownload = useCallback(async () => {
    setBulkDownloading(true);
    try {
      await bulkDownloadKnowledgeDocuments(selectedRowKeys.map((key) => Number(key)));
      setSelectedRowKeys([]);
      void loadDocuments();
    } finally {
      setBulkDownloading(false);
    }
  }, [loadDocuments, selectedRowKeys]);

  const handleDeleteDocument = useCallback(async (item: KnowledgeDocumentRecord) => {
    setDeletingDocumentId(item.id);
    try {
      await deleteKnowledgeDocument(item.id);
      message.success('文档已删除');
      setSelectedRowKeys((current) => current.filter((key) => Number(key) !== item.id));
      void loadDocuments();
      void loadBases();
    } finally {
      setDeletingDocumentId(null);
    }
  }, [loadBases, loadDocuments]);

  const handleDeleteBase = useCallback(async (item: KnowledgeBaseRecord) => {
    setDeletingBaseId(item.id);
    try {
      await deleteKnowledgeBase(item.id);
      message.success('知识库已删除');
      if (selectedBase?.id === item.id) {
        setSelectedBase(null);
        setDocuments([]);
      }
      void loadBases();
    } finally {
      setDeletingBaseId(null);
    }
  }, [loadBases, selectedBase]);

  const handleIndexDocument = useCallback(async (item: KnowledgeDocumentRecord) => {
    setIndexingDocumentId(item.id);
    try {
      await indexKnowledgeDocument(item.id);
      message.success('索引任务已触发');
      void loadDocuments();
      void loadBases();
    } finally {
      setIndexingDocumentId(null);
    }
  }, [loadBases, loadDocuments]);

  const handleIndexBase = useCallback(async () => {
    if (!selectedBase) return;
    setIndexingBase(true);
    try {
      const result = await indexKnowledgeBase(selectedBase.id);
      message.success(`已触发 ${result.queuedCount} 个文档的索引任务`);
      void loadDocuments();
      void loadBases();
    } finally {
      setIndexingBase(false);
    }
  }, [loadBases, loadDocuments, selectedBase]);

  const handleRecallTest = useCallback(async () => {
    if (!selectedBase || !recallQuery.trim()) {
      message.warning('请输入召回测试问题');
      return;
    }
    setRecallLoading(true);
    try {
      const result = await recallTestKnowledgeBase(selectedBase.id, {
        query: recallQuery.trim(),
        topN: recallTopN,
      });
      const modeLabel = result.mode === 'vector' ? '向量召回' : result.mode === 'keyword' ? '关键词召回' : '无命中';
      setRecallChunks(result.chunks);
      setRecallMode(modeLabel);
      setRecallHistory((current) => [
        {
          id: `${selectedBase.id}-${Date.now()}`,
          query: recallQuery.trim(),
          mode: modeLabel,
          count: result.chunks.length,
        },
        ...current,
      ].slice(0, 10));
    } finally {
      setRecallLoading(false);
    }
  }, [recallQuery, recallTopN, selectedBase]);

  const baseColumns = useMemo<ColumnsType<KnowledgeBaseRecord>>(() => [
    {
      title: '知识库',
      key: 'name',
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{item.name}</Typography.Text>
          <Typography.Text className="!text-xs !text-slate-500">{item.description || '暂无描述'}</Typography.Text>
        </Space>
      ),
    },
    {
      title: '文档',
      key: 'documentCount',
      width: 120,
      render: (_, item) => item.documentCount,
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 100,
      render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
    },
    {
      title: '操作',
      key: 'actions',
      width: 190,
      render: (_, item) => (
        <Space size={0}>
          <Button type="link" onClick={() => setSelectedBase(item)}>
            进入
          </Button>
          <Button type="link" icon={<EditOutlined />} disabled={!canUpload} onClick={() => openEditBase(item)}>
            编辑
          </Button>
          <Popconfirm
            title="删除知识库"
            description={`确认删除“${item.name}”及其文档吗？`}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: deletingBaseId === item.id }}
            disabled={!canDelete}
            onConfirm={() => void handleDeleteBase(item)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} disabled={!canDelete} loading={deletingBaseId === item.id}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ], [canDelete, canUpload, deletingBaseId, handleDeleteBase, openEditBase]);

  const documentColumns = useMemo<ColumnsType<KnowledgeDocumentRecord>>(() => [
    {
      title: '文档',
      key: 'document',
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{item.title}</Typography.Text>
          <Typography.Text className="!text-xs !text-slate-500">{item.fileName}</Typography.Text>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'fileExtension',
      width: 90,
      render: (value: string) => <Tag>{value ? value.toUpperCase() : '--'}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'fileSize',
      width: 110,
      render: (value: number | null) => formatFileSize(value),
    },
    {
      title: '上传人',
      dataIndex: 'uploadedBy',
      width: 120,
      render: (value: string) => value || '--',
    },
    {
      title: '下载',
      dataIndex: 'downloadCount',
      width: 80,
    },
    {
      title: '索引',
      key: 'indexingStatus',
      width: 150,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Tag color={indexStatusColor[item.indexingStatus]}>{item.indexingStatusLabel || item.indexingStatus}</Tag>
          <Typography.Text className="!text-xs !text-slate-500">{item.chunkCount} 块</Typography.Text>
        </Space>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
    },
    {
      title: '操作',
      key: 'actions',
      width: 300,
      render: (_, item) => (
        <Space size={0}>
          <Button
            type="link"
            icon={<DownloadOutlined />}
            disabled={!canDownload}
            loading={downloadLoadingId === item.id}
            onClick={() => void handleSingleDownload(item)}
          >
            下载
          </Button>
          <Button
            type="link"
            icon={<BranchesOutlined />}
            disabled={!canUpload}
            loading={indexingDocumentId === item.id}
            onClick={() => void handleIndexDocument(item)}
          >
            重建索引
          </Button>
          <Popconfirm
            title="删除文档"
            description={`确认删除“${item.title}”吗？`}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: deletingDocumentId === item.id }}
            disabled={!canDelete}
            onConfirm={() => void handleDeleteDocument(item)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} disabled={!canDelete} loading={deletingDocumentId === item.id}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ], [
    canDelete,
    canDownload,
    canUpload,
    deletingDocumentId,
    downloadLoadingId,
    handleDeleteDocument,
    handleIndexDocument,
    handleSingleDownload,
    indexingDocumentId,
  ]);

  const editBaseModal = (
    <Modal
      title="编辑知识库"
      open={editOpen}
      confirmLoading={editSaving}
      onOk={() => void handleEditBase()}
      onCancel={() => {
        setEditOpen(false);
        setEditingBase(null);
      }}
      okText="保存"
      cancelText="取消"
    >
      <Form form={editForm} layout="vertical">
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入知识库名称' }]}>
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea maxLength={255} rows={3} placeholder="说明资料范围、维护责任人或适用业务场景" />
        </Form.Item>
      </Form>
    </Modal>
  );

  const documentManagementTab = (
    <Space direction="vertical" size={16} className="w-full">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={14} className="w-full">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <Typography.Title level={5} className="!mb-1">文档管理</Typography.Title>
                <Typography.Text className="!text-sm !text-slate-500">按资料集维护原始文件，上传后进入解析、切分、索引流程。</Typography.Text>
              </div>
              <Upload.Dragger
                multiple
                showUploadList={false}
                accept={KNOWLEDGE_BASE_ACCEPT}
                disabled={!canUpload || hasInFlightUpload}
                beforeUpload={(file) => {
                  enqueueFiles([file as File]);
                  return Upload.LIST_IGNORE;
                }}
                className="!w-full md:!w-[300px]"
              >
                <p className="ant-upload-drag-icon !mb-2"><InboxOutlined /></p>
                <p className="ant-upload-text !text-sm">拖拽或点击上传</p>
                <p className="ant-upload-hint !text-xs">最多 3 个文件并发，支持 {KNOWLEDGE_BASE_ACCEPT}</p>
              </Upload.Dragger>
            </div>

            {uploadTasks.length > 0 ? (
              <div className="space-y-3">
                {uploadTasks.map((task) => (
                  <div key={task.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <Typography.Text strong>{task.file.name}</Typography.Text>
                      <Tag color={task.status === 'success' ? 'success' : task.status === 'error' ? 'error' : 'processing'}>
                        {task.status === 'pending' && '等待上传'}
                        {task.status === 'uploading' && '上传中'}
                        {task.status === 'success' && '上传成功'}
                        {task.status === 'error' && '上传失败'}
                      </Tag>
                    </div>
                    <Progress percent={task.progress} size="small" status={task.status === 'error' ? 'exception' : undefined} />
                    {task.error ? <Typography.Text className="!text-xs !text-red-500">{task.error}</Typography.Text> : null}
                  </div>
                ))}
              </div>
            ) : (
              <Alert showIcon type="info" message="还没有本次上传任务" description="上传后的文档会出现在下方表格，可下载、批量下载或删除。" />
            )}
          </Space>
        </Card>

        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={14} className="w-full">
            <Typography.Title level={5} className="!mb-0">索引流程</Typography.Title>
            {detailWorkflow.map((item, index) => (
              <div key={item.title} className="flex gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-600 text-sm font-semibold text-white">{index + 1}</div>
                <div>
                  <Typography.Text strong className="!text-sm">{item.title}</Typography.Text>
                  <Typography.Paragraph className="!mb-0 !mt-1 !text-xs !text-slate-500">{item.description}</Typography.Paragraph>
                </div>
              </div>
            ))}
          </Space>
        </Card>
      </div>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={documentsLoading}
          columns={documentColumns}
          dataSource={documents}
          rowSelection={canBulkDownload ? { selectedRowKeys, onChange: setSelectedRowKeys } : undefined}
          pagination={false}
          locale={{ emptyText: '当前知识库暂无文档' }}
          scroll={{ x: 1120 }}
        />
      </Card>
    </Space>
  );

  const recallTestTab = (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={12} className="w-full">
          <div className="flex items-center gap-2">
            <FileSearchOutlined className="text-teal-700" />
            <Typography.Title level={5} className="!mb-0">召回测试</Typography.Title>
          </div>
          <Typography.Text className="!text-sm !text-slate-500">先用真实业务问题验证命中片段，再绑定给智能体。</Typography.Text>
          <Input.TextArea rows={5} value={recallQuery} onChange={(event) => setRecallQuery(event.target.value)} placeholder="输入问题，例如：设备离线后客户应该如何处理？" />
          <div className="flex items-center justify-between gap-3">
            <Space>
              <Typography.Text className="!text-sm !text-slate-500">Top N</Typography.Text>
              <InputNumber min={1} max={20} value={recallTopN} onChange={(value) => setRecallTopN(Number(value || 5))} />
            </Space>
            <Button type="primary" icon={<CloudUploadOutlined />} loading={recallLoading} onClick={() => void handleRecallTest()}>测试召回</Button>
          </div>
          {recallMode ? <Tag color={recallMode === '向量召回' ? 'green' : 'blue'}>{recallMode}</Tag> : null}
          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <Typography.Text strong className="!text-sm">最近测试</Typography.Text>
            <div className="mt-3 space-y-2">
              {recallHistory.length > 0 ? recallHistory.map((item) => (
                <button key={item.id} type="button" className="w-full rounded-lg border border-slate-100 bg-white px-3 py-2 text-left text-sm transition hover:border-teal-200 hover:bg-teal-50/50" onClick={() => setRecallQuery(item.query)}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-slate-700">{item.query}</span>
                    <Tag>{item.count} 条</Tag>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{item.mode}</div>
                </button>
              )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无测试历史" />}
            </div>
          </div>
        </Space>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={12} className="w-full">
          <Typography.Title level={5} className="!mb-0">命中片段</Typography.Title>
          <div className="max-h-[560px] overflow-y-auto pr-1">
            {recallChunks.length > 0 ? (
              <Space direction="vertical" size={10} className="w-full">
                {recallChunks.map((chunk, index) => (
                  <div key={`${chunk.documentId}-${chunk.chunkIndex}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <Typography.Text strong className="!text-sm">{chunk.documentTitle}</Typography.Text>
                      <Tag color="green">score {chunk.score.toFixed(4)}</Tag>
                    </div>
                    <Typography.Paragraph className="!mb-0 !text-sm !text-slate-600">{chunk.content}</Typography.Paragraph>
                  </div>
                ))}
              </Space>
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无召回结果" />}
          </div>
        </Space>
      </Card>
    </div>
  );

  const indexPolicyTab = (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      {retrievalPolicies.map((item) => (
        <Card key={item.title} variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={10}>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-700"><BranchesOutlined /></div>
            <Typography.Title level={5} className="!mb-0">{item.title}</Typography.Title>
            <Typography.Paragraph className="!mb-0 !text-sm !text-slate-500">{item.description}</Typography.Paragraph>
          </Space>
        </Card>
      ))}
    </div>
  );

  if (!selectedBase) {
    return (
      <Space direction="vertical" size={18} className="w-full">
        <Card variant="borderless" className="overflow-hidden !rounded-xl !border !border-teal-100 !bg-gradient-to-br !from-white !via-teal-50/40 !to-slate-50 !shadow-card">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white/80 px-3 py-1 text-xs font-medium text-teal-700">
                <SafetyCertificateOutlined />
                企业知识沉淀与智能体召回中心
              </div>
              <Typography.Title level={2} className="!mb-3 !text-slate-950">知识库</Typography.Title>
              <Typography.Paragraph className="!mb-0 !max-w-2xl !text-base !text-slate-600">
                这里把“创建资料集、导入文档、验证召回、绑定智能体”收敛到一个页面，先把资料整理成可验证的知识资产，再提供给智能体使用。
              </Typography.Paragraph>
            </div>
            <Space wrap className="xl:justify-end">
              <Input.Search
                allowClear
                placeholder="搜索知识库"
                className="!w-72"
                onSearch={(value) => {
                  setBaseKeyword(value.trim());
                  setBasePage(1);
                }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => void loadBases()}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} disabled={!canUpload} onClick={() => setCreateOpen(true)}>
                创建知识库
              </Button>
            </Space>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
            {knowledgeBaseHighlights.map((item) => (
              <div key={item.label} className="rounded-xl border border-white/80 bg-white/75 p-4 shadow-sm">
                <Typography.Text strong className="!text-slate-900">{item.label}</Typography.Text>
                <Typography.Paragraph className="!mb-0 !mt-2 !text-sm !text-slate-500">{item.description}</Typography.Paragraph>
              </div>
            ))}
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div className="rounded-xl bg-slate-50 p-4">
                <Typography.Text className="!text-xs !text-slate-500">知识库总数</Typography.Text>
                <div className="mt-2 text-2xl font-semibold text-slate-950">{baseTotal}</div>
              </div>
              <div className="rounded-xl bg-teal-50 p-4">
                <Typography.Text className="!text-xs !text-teal-700">当前页启用</Typography.Text>
                <div className="mt-2 text-2xl font-semibold text-teal-800">{activeBaseCount}</div>
              </div>
              <div className="rounded-xl bg-blue-50 p-4">
                <Typography.Text className="!text-xs !text-blue-700">当前页文档</Typography.Text>
                <div className="mt-2 text-2xl font-semibold text-blue-800">{visibleDocumentCount}</div>
              </div>
              <div className="rounded-xl bg-violet-50 p-4">
                <Typography.Text className="!text-xs !text-violet-700">最近更新</Typography.Text>
                <div className="mt-2 truncate text-sm font-semibold text-violet-800">{latestUpdatedAt || '--'}</div>
              </div>
            </div>
          </Card>

          <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
            <Space direction="vertical" size={10} className="w-full">
              <Typography.Title level={5} className="!mb-0">推荐流程</Typography.Title>
              {createGuideCards.map((item) => (
                <div key={item.title} className="flex gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-teal-700 shadow-sm">
                    {item.icon}
                  </div>
                  <div>
                    <Typography.Text strong className="!text-sm">{item.title}</Typography.Text>
                    <Typography.Paragraph className="!mb-0 !mt-1 !text-xs !text-slate-500">{item.description}</Typography.Paragraph>
                  </div>
                </div>
              ))}
            </Space>
          </Card>
        </div>

        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Table
            rowKey="id"
            loading={baseLoading}
            columns={baseColumns}
            dataSource={bases}
            pagination={{
              current: basePage,
              pageSize: PAGE_SIZE,
              total: baseTotal,
              showSizeChanger: false,
              onChange: setBasePage,
            }}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={baseKeyword ? '没有匹配的知识库' : '还没有知识库，先创建一个用于沉淀业务资料'}
                />
              ),
            }}
          />
        </Card>

        <Modal
          title="创建知识库"
          open={createOpen}
          confirmLoading={createSaving}
          onOk={() => void handleCreateBase()}
          onCancel={() => setCreateOpen(false)}
          okText="创建"
          cancelText="取消"
        >
          <Form form={createForm} layout="vertical">
            <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入知识库名称' }]}>
              <Input maxLength={128} placeholder="例如：售后政策知识库" />
            </Form.Item>
            <Form.Item name="description" label="说明">
              <Input.TextArea maxLength={255} rows={3} placeholder="用于区分业务场景、资料范围或维护责任人" />
            </Form.Item>
          </Form>
        </Modal>

        {editBaseModal}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <Space size={12} align="start">
            <Button icon={<ArrowLeftOutlined />} onClick={() => setSelectedBase(null)} />
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">{selectedBase.name}</Typography.Title>
              <Typography.Text className="!text-slate-500">{selectedBase.description || '暂无描述'}</Typography.Text>
              <div className="mt-2 flex gap-2">
                <Tag color="blue">文档 {selectedBase.documentCount}</Tag>
                <Tag color={selectedBase.isActive ? 'success' : 'default'}>{selectedBase.isActive ? '可用于智能体' : '已停用'}</Tag>
              </div>
            </div>
          </Space>
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索标题 / 文件名"
              className="!w-72"
              onSearch={(value) => setDocumentKeyword(value.trim())}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadDocuments()}>刷新</Button>
            <Button
              icon={<BranchesOutlined />}
              disabled={!canUpload}
              loading={indexingBase}
              onClick={() => void handleIndexBase()}
            >
              重建索引
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              disabled={!canBulkDownload || selectedRowKeys.length === 0}
              loading={bulkDownloading}
              onClick={() => void handleBulkDownload()}
            >
              批量下载
            </Button>
          </Space>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Statistic title="当前文档" value={selectedBase.documentCount} suffix="份" />
            <Statistic title="已选文档" value={selectedRowKeys.length} suffix="份" />
            <Statistic title="召回 Top N" value={recallTopN} />
            <Statistic title="测试记录" value={recallHistory.length} suffix="次" />
          </div>
        </Card>
        <Alert
          showIcon
          type="info"
          className="!rounded-xl !border-blue-100 !bg-blue-50"
          message="上线前建议"
          description="先用真实高频问题完成召回验证，确认片段来源可靠后再绑定到智能体应用。"
        />
      </div>

      <Tabs
        items={[
          { key: 'documents', label: '文档管理', children: documentManagementTab },
          { key: 'recall', label: '召回测试', children: recallTestTab },
          { key: 'policy', label: '索引策略', children: indexPolicyTab },
        ]}
      />
    </Space>
  );
};
