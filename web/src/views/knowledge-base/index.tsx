import type { Key } from 'react';
import {
  ArrowLeftOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  InboxOutlined,
  PlusOutlined,
  ReloadOutlined,
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
  Progress,
  Space,
  Table,
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
  recallTestKnowledgeBase,
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

const PAGE_SIZE = 10;
const MAX_UPLOAD_CONCURRENCY = 3;

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
  const [createForm] = Form.useForm<{ name: string; description?: string }>();

  const [documents, setDocuments] = useState<KnowledgeDocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentKeyword, setDocumentKeyword] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [downloadLoadingId, setDownloadLoadingId] = useState<number | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null);
  const [deletingBaseId, setDeletingBaseId] = useState<number | null>(null);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const uploadTasksRef = useRef<UploadTask[]>([]);

  const [recallQuery, setRecallQuery] = useState('');
  const [recallTopN, setRecallTopN] = useState(5);
  const [recallLoading, setRecallLoading] = useState(false);
  const [recallChunks, setRecallChunks] = useState<KnowledgeRecallChunk[]>([]);
  const [recallMode, setRecallMode] = useState('');

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
      setRecallChunks(result.chunks);
      setRecallMode(result.mode === 'vector' ? '向量召回' : result.mode === 'keyword' ? '关键词召回' : '无命中');
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
  ], [canDelete, deletingBaseId, handleDeleteBase]);

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
    deletingDocumentId,
    downloadLoadingId,
    handleDeleteDocument,
    handleSingleDownload,
  ]);

  if (!selectedBase) {
    return (
      <Space direction="vertical" size={18} className="w-full">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <Space size={12} align="center">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
                <FileSearchOutlined className="text-lg" />
              </div>
              <div>
                <Typography.Title level={3} className="!mb-1 !text-slate-900">知识库</Typography.Title>
                <Typography.Text className="!text-slate-500">创建知识库后进入详情上传文件并执行召回测试。</Typography.Text>
              </div>
            </Space>
            <Space wrap>
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
        </Card>

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
            locale={{ emptyText: '暂无知识库，请先创建' }}
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

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.7fr)]">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={14} className="w-full">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <Typography.Title level={5} className="!mb-0">文档上传</Typography.Title>
              <Upload
                multiple
                showUploadList={false}
                accept={KNOWLEDGE_BASE_ACCEPT}
                disabled={!canUpload || hasInFlightUpload}
                beforeUpload={(file) => {
                  enqueueFiles([file as File]);
                  return Upload.LIST_IGNORE;
                }}
              >
                <Button type="primary" icon={<InboxOutlined />} disabled={!canUpload || hasInFlightUpload}>
                  {hasInFlightUpload ? '上传进行中' : '选择文档'}
                </Button>
              </Upload>
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
              <Empty description="请选择文档上传" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Space>
        </Card>

        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={12} className="w-full">
            <Typography.Title level={5} className="!mb-0">召回测试</Typography.Title>
            <Input.TextArea
              rows={4}
              value={recallQuery}
              onChange={(event) => setRecallQuery(event.target.value)}
              placeholder="输入问题，测试当前知识库会召回哪些片段"
            />
            <div className="flex items-center justify-between gap-3">
              <InputNumber min={1} max={20} value={recallTopN} onChange={(value) => setRecallTopN(Number(value || 5))} />
              <Button type="primary" icon={<CloudUploadOutlined />} loading={recallLoading} onClick={() => void handleRecallTest()}>
                测试召回
              </Button>
            </div>
            {recallMode ? <Tag color={recallMode === '向量召回' ? 'green' : 'blue'}>{recallMode}</Tag> : null}
            <div className="max-h-[360px] overflow-y-auto pr-1">
              {recallChunks.length > 0 ? (
                <Space direction="vertical" size={10} className="w-full">
                  {recallChunks.map((chunk, index) => (
                    <div key={`${chunk.documentId}-${chunk.chunkIndex}-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <Typography.Text strong className="!text-sm">{chunk.documentTitle}</Typography.Text>
                        <Tag>{chunk.score.toFixed(4)}</Tag>
                      </div>
                      <Typography.Paragraph className="!mb-0 !text-sm !text-slate-600">{chunk.content}</Typography.Paragraph>
                    </div>
                  ))}
                </Space>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无召回结果" />
              )}
            </div>
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
};
