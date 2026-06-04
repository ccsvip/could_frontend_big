import type { Key } from 'react';
import {
  CheckOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  CloseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FileOutlined,
  InboxOutlined,
  ReloadOutlined,
  StopOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Empty,
  Input,
  Popconfirm,
  Progress,
  Select,
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
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  fetchKnowledgeDocuments,
  reviewKnowledgeDocument,
  uploadKnowledgeDocument,
  type KnowledgeDocumentListQuery,
  type KnowledgeDocumentRecord,
  type KnowledgeDocumentStatus,
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

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待审核', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
] as const;

const formatFileSize = (value: number | null) => {
  if (value === null || value === undefined) {
    return '--';
  }

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};

const getStatusTag = (status: KnowledgeDocumentStatus) => {
  if (status === 'approved') {
    return { color: 'success', icon: <CheckCircleOutlined />, text: '已通过' };
  }

  if (status === 'rejected') {
    return { color: 'error', icon: <StopOutlined />, text: '已拒绝' };
  }

  return { color: 'processing', icon: <ClockCircleOutlined />, text: '待审核' };
};

export const KnowledgeBasePage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canUpload = hasPermission('knowledge_base.upload');
  const canDownload = hasPermission('knowledge_base.download');
  const canBulkDownload = hasPermission('knowledge_base.bulk_download');
  const canReview = hasPermission('tenant.management.view');
  const canDelete = canUpload;

  const [items, setItems] = useState<KnowledgeDocumentRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [processingStatus, setProcessingStatus] = useState<KnowledgeDocumentStatus | 'all'>('all');
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [downloadLoadingId, setDownloadLoadingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [reviewLoadingId, setReviewLoadingId] = useState<number | null>(null);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const uploadTasksRef = useRef<UploadTask[]>([]);

  useEffect(() => {
    uploadTasksRef.current = uploadTasks;
  }, [uploadTasks]);

  const query = useMemo<KnowledgeDocumentListQuery>(
    () => ({
      page,
      keyword,
      processingStatus,
    }),
    [keyword, page, processingStatus],
  );

  const loadData = useCallback(
    async (nextQuery: KnowledgeDocumentListQuery = query) => {
      setLoading(true);
      try {
        const response = await fetchKnowledgeDocuments(nextQuery);
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

  const startUpload = useCallback(
    async (taskId: string) => {
      const task = uploadTasksRef.current.find((item) => item.id === taskId);
      if (!task) {
        return;
      }

      setUploadTasks((current) =>
        current.map((item) => (item.id === taskId ? { ...item, status: 'uploading', progress: 0, error: undefined } : item)),
      );

      try {
        await uploadKnowledgeDocument(
          { file: task.file },
          {
            timeoutMs: 120000,
            onUploadProgress: (percent) => {
              setUploadTasks((current) =>
                current.map((item) => (item.id === taskId ? { ...item, progress: percent } : item)),
              );
            },
          },
        );

        setUploadTasks((current) =>
          current.map((item) => (item.id === taskId ? { ...item, status: 'success', progress: 100 } : item)),
        );
        message.success('文档已上传，等待管理员审核');
        setPage(1);
        void loadData({ ...query, page: 1 });
      } catch (error) {
        const nextError = error instanceof Error ? error.message : '上传失败';
        setUploadTasks((current) =>
          current.map((item) => (item.id === taskId ? { ...item, status: 'error', error: nextError } : item)),
        );
      }
    },
    [loadData, query],
  );

  useEffect(() => {
    const uploadingCount = uploadTasks.filter((item) => item.status === 'uploading').length;
    if (uploadingCount >= MAX_UPLOAD_CONCURRENCY) {
      return;
    }

    const pendingTasks = uploadTasks
      .filter((item) => item.status === 'pending')
      .slice(0, MAX_UPLOAD_CONCURRENCY - uploadingCount);

    pendingTasks.forEach((task) => {
      void startUpload(task.id);
    });
  }, [startUpload, uploadTasks]);

  const enqueueFiles = (files: File[]) => {
    if (files.length === 0) {
      return;
    }

    setUploadTasks((current) => [
      ...current,
      ...files.map((file) => ({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
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
      void loadData();
    } finally {
      setDownloadLoadingId(null);
    }
  }, [loadData]);

  const handleBulkDownload = useCallback(async () => {
    setBulkDownloading(true);
    try {
      await bulkDownloadKnowledgeDocuments(selectedRowKeys.map((key) => Number(key)));
      setSelectedRowKeys([]);
      void loadData();
    } finally {
      setBulkDownloading(false);
    }
  }, [loadData, selectedRowKeys]);

  const handleDelete = useCallback(async (item: KnowledgeDocumentRecord) => {
    setDeletingId(item.id);
    try {
      await deleteKnowledgeDocument(item.id);
      message.success('文档已删除');
      setSelectedRowKeys((current) => current.filter((key) => Number(key) !== item.id));

      const nextPage = items.length === 1 && page > 1 ? page - 1 : page;
      if (nextPage !== page) {
        setPage(nextPage);
        return;
      }

      void loadData({ ...query, page: nextPage });
    } finally {
      setDeletingId(null);
    }
  }, [items.length, loadData, page, query]);

  const handleReview = useCallback(
    async (item: KnowledgeDocumentRecord, processingStatus: Extract<KnowledgeDocumentStatus, 'approved' | 'rejected'>) => {
      setReviewLoadingId(item.id);
      try {
        const response = await reviewKnowledgeDocument(item.id, { processingStatus });
        if (response.data) {
          setItems((current) => current.map((record) => (record.id === response.data?.id ? response.data : record)));
        } else {
          void loadData();
        }
        message.success(response.message || (processingStatus === 'approved' ? '审核已通过' : '审核已拒绝'));
      } catch {
        // 错误由拦截器统一提示
      } finally {
        setReviewLoadingId(null);
      }
    },
    [loadData],
  );

  const columns = useMemo<ColumnsType<KnowledgeDocumentRecord>>(
    () => [
      {
        title: '文档',
        key: 'document',
        render: (_, item) => (
          <Space direction="vertical" size={4} className="w-full">
            <Typography.Text strong className="!text-slate-900">
              {item.title}
            </Typography.Text>
            <Typography.Text className="!text-xs !text-slate-500">
              {item.fileName}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: '类型',
        dataIndex: 'fileExtension',
        key: 'fileExtension',
        width: 100,
        render: (value: string) => <Tag>{value ? value.toUpperCase() : '--'}</Tag>,
      },
      {
        title: '大小',
        dataIndex: 'fileSize',
        key: 'fileSize',
        width: 110,
        render: (value: number | null) => formatFileSize(value),
      },
      {
        title: '处理状态',
        dataIndex: 'processingStatus',
        key: 'processingStatus',
        width: 140,
        render: (value: KnowledgeDocumentStatus, item) => {
          const tag = getStatusTag(value);
          return (
            <Tag color={tag.color} icon={tag.icon}>
              {item.processingStatusLabel || tag.text}
            </Tag>
          );
        },
      },
      {
        title: '上传人',
        dataIndex: 'uploadedBy',
        key: 'uploadedBy',
        width: 140,
        render: (value: string) => value || '--',
      },
      {
        title: '下载次数',
        dataIndex: 'downloadCount',
        key: 'downloadCount',
        width: 100,
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
        width: 320,
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
            {canReview ? (
              <>
                <Button
                  type="link"
                  icon={<CheckOutlined />}
                  disabled={item.processingStatus !== 'pending'}
                  loading={reviewLoadingId === item.id}
                  onClick={() => void handleReview(item, 'approved')}
                >
                  通过
                </Button>
                <Button
                  type="link"
                  danger
                  icon={<CloseOutlined />}
                  disabled={item.processingStatus !== 'pending'}
                  loading={reviewLoadingId === item.id}
                  onClick={() => void handleReview(item, 'rejected')}
                >
                  拒绝
                </Button>
              </>
            ) : null}
            <Popconfirm
              title="删除文档"
              description={`确认删除“${item.title}”吗？删除后不可恢复。`}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true, loading: deletingId === item.id }}
              disabled={!canDelete}
              onConfirm={() => void handleDelete(item)}
            >
              <Button
                type="link"
                danger
                icon={<DeleteOutlined />}
                disabled={!canDelete}
                loading={deletingId === item.id}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [canDelete, canDownload, canReview, deletingId, downloadLoadingId, handleDelete, handleReview, handleSingleDownload, reviewLoadingId],
  );

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <Space size={12} align="center">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-teal-50 to-teal-100/60 text-teal-700">
                <CloudUploadOutlined className="text-lg" />
              </div>
              <div>
                <Typography.Title level={3} className="!mb-1 !text-slate-900">
                  知识库
                </Typography.Title>
                <Typography.Text className="!text-slate-500">
                  支持多文件并发上传、单个下载、批量下载、删除已上传文档，以及管理员在后台维护审核状态。
                </Typography.Text>
              </div>
            </Space>
          </div>

          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索标题 / 文件名"
              className="!w-72"
              onSearch={(value) => {
                setKeyword(value.trim());
                setPage(1);
              }}
            />
            <Select
              value={processingStatus}
              options={statusOptions as unknown as { label: string; value: string }[]}
              onChange={(value) => {
                setProcessingStatus(value as KnowledgeDocumentStatus | 'all');
                setPage(1);
              }}
              className="!w-36"
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>
              刷新
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

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={14} className="w-full">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <Typography.Title level={5} className="!mb-1 !text-slate-900">
                文档上传
              </Typography.Title>
              <Typography.Text className="!text-slate-500">
                单次选择多个文档后，系统最多同时并发上传 3 个文件；上传成功后将显示本地提示“文档已上传，等待管理员审核”。
              </Typography.Text>
            </div>
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
                <div
                  key={task.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
                >
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <Space size={10}>
                      <FileOutlined className="text-slate-500" />
                      <div>
                        <Typography.Text strong className="!text-slate-900">
                          {task.file.name}
                        </Typography.Text>
                        <Typography.Text className="!ml-2 !text-xs !text-slate-500">
                          {formatFileSize(task.file.size)}
                        </Typography.Text>
                      </div>
                    </Space>
                    <Tag color={task.status === 'success' ? 'success' : task.status === 'error' ? 'error' : 'processing'}>
                      {task.status === 'pending' && '等待上传'}
                      {task.status === 'uploading' && '上传中'}
                      {task.status === 'success' && '上传成功'}
                      {task.status === 'error' && '上传失败'}
                    </Tag>
                  </div>
                  <Progress percent={task.progress} size="small" status={task.status === 'error' ? 'exception' : undefined} />
                  {task.error ? (
                    <Typography.Text className="!text-xs !text-red-500">{task.error}</Typography.Text>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <Empty description="请选择知识库文档进行上传" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Space>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          rowSelection={
            canBulkDownload
              ? {
                  selectedRowKeys,
                  onChange: setSelectedRowKeys,
                }
              : undefined
          }
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            onChange: (nextPage) => setPage(nextPage),
          }}
          locale={{
            emptyText: keyword || processingStatus !== 'all' ? '当前筛选条件下暂无文档' : '暂无知识库文档，请先上传',
          }}
          scroll={{ x: 1180 }}
        />
      </Card>
    </Space>
  );
};
