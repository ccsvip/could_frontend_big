import React from 'react';
import type { Key } from 'react';
import {
  IconArrowLeft,
  IconArrowRight,
  IconBook,
  IconCloudUpload,
  IconCompass,
  IconDatabase,
  IconDownload,
  IconFilePlus,
  IconFileSearch,
  IconFlask,
  IconGitBranch,
  IconPencil,
  IconPhoto,
  IconPlus,
  IconRefresh,
  IconShieldCheck,
  IconAdjustments,
  IconStack2,
  IconTrash,
  IconVideo,
} from '@tabler/icons-react';
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
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
  Pagination,
  Spin,
  Switch,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  KNOWLEDGE_BASE_ACCEPT,
  bindKnowledgeMediaAssets,
  bulkDownloadKnowledgeDocuments,
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  deleteKnowledgeMediaAsset,
  downloadKnowledgeDocument,
  fetchKnowledgeBaseDocuments,
  fetchKnowledgeBases,
  fetchKnowledgeMediaAssets,
  indexKnowledgeBase,
  indexKnowledgeDocument,
  recallTestKnowledgeBase,
  updateKnowledgeBase,
  updateKnowledgeMediaAsset,
  uploadKnowledgeBaseDocument,
  type KnowledgeBaseListQuery,
  type KnowledgeBaseRecord,
  type KnowledgeDocumentListQuery,
  type KnowledgeDocumentRecord,
  type KnowledgeMediaAssetRecord,
  type KnowledgeRecallChunk,
} from '../../api/modules/knowledge-base';
import {
  fetchImageResources,
  fetchVideoResources,
  type ResourceRecord,
} from '../../api/modules/resources';
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
  chunkSize?: number;
  chunkOverlap?: number;
  retrievalTopN?: number;
  retrievalMinScore?: number;
  mediaMaxAssets?: number;
  mediaMinRelevance?: number;
};

type MediaAssetFormValues = {
  keywords?: string;
  description?: string;
  isEnabled?: boolean;
  priority?: number;
};

type RecallHistoryItem = {
  id: string;
  query: string;
  mode: string;
  count: number;
};

const PAGE_SIZE = 10;
const MAX_UPLOAD_CONCURRENCY = 3;



const createGuideCards = [
  {
    title: '创建业务知识库',
    description: '按业务域、产品线或部门拆分知识库，方便权限隔离和后续维护。',
    icon: <IconBook />,
    iconColor: 'text-teal-600',
    iconBg: 'bg-teal-50',
  },
  {
    title: '上传并维护文档',
    description: `当前支持 ${KNOWLEDGE_BASE_ACCEPT.replace(/\./g, '').toUpperCase()}，建议文件名保留版本和适用范围。`,
    icon: <IconFilePlus />,
    iconColor: 'text-slate-600',
    iconBg: 'bg-slate-100',
  },
  {
    title: '测试召回效果',
    description: '用真实用户问题检查命中内容，再把知识库绑定到智能体应用。',
    icon: <IconFlask />,
    iconColor: 'text-slate-600',
    iconBg: 'bg-slate-100',
  },
];

const detailWorkflow = [
  { title: '上传资料', description: '拖入或选择文档，最多 3 个文件并发上传。' },
  { title: '等待处理', description: '后台完成解析、切分和索引后即可参与召回。' },
  { title: '验证命中', description: '用典型问题测试 Top N 片段，确认答案来源可靠。' },
];

const indexStatusColor: Record<KnowledgeDocumentRecord['indexingStatus'], string> = {
  pending: 'default',
  indexing: 'processing',
  ready: 'success',
  failed: 'error',
};

const defaultIndexConfig = {
  chunkSize: 500,
  chunkOverlap: 50,
  retrievalTopN: 5,
  retrievalMinScore: 0.2,
  mediaMaxAssets: 0,
  mediaMinRelevance: 0.22,
};

const recallModeText: Record<string, string> = {
  vector: '向量召回',
  keyword: '关键词召回',
  empty: '无命中',
  skipped: '未进入知识库检索',
};

const recallModeColor: Record<string, string> = {
  vector: 'success',
  keyword: 'processing',
  empty: 'default',
  skipped: 'warning',
};

const skipReasonText: Record<string, string> = {
  low_information_query: '问题信息量较少，系统不会用它去匹配知识库或配套素材。',
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
  const [recallMediaAssets, setRecallMediaAssets] = useState<KnowledgeMediaAssetRecord[]>([]);
  const [recallMode, setRecallMode] = useState('');
  const [recallModeKey, setRecallModeKey] = useState('');
  const [recallSkipReason, setRecallSkipReason] = useState('');
  const [recallHistory, setRecallHistory] = useState<RecallHistoryItem[]>([]);

  const [mediaAssets, setMediaAssets] = useState<KnowledgeMediaAssetRecord[]>([]);
  const [mediaAssetsLoading, setMediaAssetsLoading] = useState(false);
  const [bindMediaOpen, setBindMediaOpen] = useState(false);
  const [bindableResources, setBindableResources] = useState<ResourceRecord[]>([]);
  const [bindableResourcesLoading, setBindableResourcesLoading] = useState(false);
  const [selectedResourceKeys, setSelectedResourceKeys] = useState<Key[]>([]);
  const [bindingMedia, setBindingMedia] = useState(false);
  const [editingMediaAsset, setEditingMediaAsset] = useState<KnowledgeMediaAssetRecord | null>(null);
  const [mediaAssetSaving, setMediaAssetSaving] = useState(false);
  const [deletingMediaAssetId, setDeletingMediaAssetId] = useState<number | null>(null);
  const [mediaAssetForm] = Form.useForm<MediaAssetFormValues>();

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

  const loadMediaAssets = useCallback(async () => {
    if (!selectedBase) {
      setMediaAssets([]);
      return;
    }
    setMediaAssetsLoading(true);
    try {
      const response = await fetchKnowledgeMediaAssets(selectedBase.id);
      setMediaAssets(response);
    } finally {
      setMediaAssetsLoading(false);
    }
  }, [selectedBase]);

  useEffect(() => {
    void loadBases();
  }, [loadBases]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    void loadMediaAssets();
  }, [loadMediaAssets]);

  useEffect(() => {
    if (selectedBase) {
      setRecallTopN(selectedBase.retrievalTopN || defaultIndexConfig.retrievalTopN);
      setRecallChunks([]);
      setRecallMediaAssets([]);
      setRecallMode('');
      setRecallModeKey('');
      setRecallSkipReason('');
    }
  }, [selectedBase?.id, selectedBase?.retrievalTopN]);

  const handleCreateBase = async () => {
    const values = await createForm.validateFields();
    setCreateSaving(true);
    try {
      const created = await createKnowledgeBase({
        name: values.name.trim(),
        description: values.description?.trim(),
        chunkSize: values.chunkSize ?? defaultIndexConfig.chunkSize,
        chunkOverlap: values.chunkOverlap ?? defaultIndexConfig.chunkOverlap,
        retrievalTopN: values.retrievalTopN ?? defaultIndexConfig.retrievalTopN,
        retrievalMinScore: values.retrievalMinScore ?? defaultIndexConfig.retrievalMinScore,
        mediaMaxAssets: values.mediaMaxAssets ?? defaultIndexConfig.mediaMaxAssets,
        mediaMinRelevance: values.mediaMinRelevance ?? defaultIndexConfig.mediaMinRelevance,
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
  const mediaAssetStats = useMemo(() => ({
    total: mediaAssets.length,
    enabled: mediaAssets.filter((item) => item.isEnabled && !item.isMissing).length,
    ready: mediaAssets.filter((item) => item.embeddingStatus === 'ready').length,
    images: mediaAssets.filter((item) => item.resourceType === 'image').length,
    videos: mediaAssets.filter((item) => item.resourceType === 'video').length,
  }), [mediaAssets]);

  const openEditBase = useCallback((item: KnowledgeBaseRecord) => {
    setEditingBase(item);
    editForm.setFieldsValue({
      name: item.name,
      description: item.description,
      chunkSize: item.chunkSize,
      chunkOverlap: item.chunkOverlap,
      retrievalTopN: item.retrievalTopN,
      retrievalMinScore: item.retrievalMinScore ?? defaultIndexConfig.retrievalMinScore,
      mediaMaxAssets: item.mediaMaxAssets ?? defaultIndexConfig.mediaMaxAssets,
      mediaMinRelevance: item.mediaMinRelevance ?? defaultIndexConfig.mediaMinRelevance,
    });
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
        chunkSize: values.chunkSize ?? defaultIndexConfig.chunkSize,
        chunkOverlap: values.chunkOverlap ?? defaultIndexConfig.chunkOverlap,
        retrievalTopN: values.retrievalTopN ?? defaultIndexConfig.retrievalTopN,
        retrievalMinScore: values.retrievalMinScore ?? defaultIndexConfig.retrievalMinScore,
        mediaMaxAssets: values.mediaMaxAssets ?? defaultIndexConfig.mediaMaxAssets,
        mediaMinRelevance: values.mediaMinRelevance ?? defaultIndexConfig.mediaMinRelevance,
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

  const openBindMediaModal = useCallback(async () => {
    setBindMediaOpen(true);
    setSelectedResourceKeys([]);
    setBindableResourcesLoading(true);
    try {
      const [images, videos] = await Promise.all([
        fetchImageResources({ pageSize: 100 }),
        fetchVideoResources({ pageSize: 100 }),
      ]);
      const boundIds = new Set(mediaAssets.map((item) => item.resourceId).filter(Boolean));
      setBindableResources(
        [...images.results, ...videos.results].filter((resource) => !boundIds.has(resource.id)),
      );
    } finally {
      setBindableResourcesLoading(false);
    }
  }, [mediaAssets]);

  const handleBindMediaAssets = useCallback(async () => {
    if (!selectedBase || selectedResourceKeys.length === 0) {
      message.warning('请选择要绑定的图片或视频素材');
      return;
    }
    setBindingMedia(true);
    try {
      await bindKnowledgeMediaAssets(selectedBase.id, selectedResourceKeys.map((key) => Number(key)));
      message.success('配套素材已绑定');
      setBindMediaOpen(false);
      setSelectedResourceKeys([]);
      await loadMediaAssets();
    } finally {
      setBindingMedia(false);
    }
  }, [loadMediaAssets, selectedBase, selectedResourceKeys]);

  const openEditMediaAsset = useCallback((item: KnowledgeMediaAssetRecord) => {
    setEditingMediaAsset(item);
    mediaAssetForm.setFieldsValue({
      keywords: item.keywords,
      description: item.description,
      isEnabled: item.isEnabled,
      priority: item.priority,
    });
  }, [mediaAssetForm]);

  const handleSaveMediaAsset = useCallback(async () => {
    if (!selectedBase || !editingMediaAsset) return;
    const values = await mediaAssetForm.validateFields();
    setMediaAssetSaving(true);
    try {
      await updateKnowledgeMediaAsset(selectedBase.id, editingMediaAsset.id, {
        keywords: values.keywords?.trim() || '',
        description: values.description?.trim() || '',
        isEnabled: values.isEnabled ?? true,
        priority: values.priority ?? 0,
      });
      message.success('配套素材已更新');
      setEditingMediaAsset(null);
      await loadMediaAssets();
    } finally {
      setMediaAssetSaving(false);
    }
  }, [editingMediaAsset, loadMediaAssets, mediaAssetForm, selectedBase]);

  const handleDeleteMediaAsset = useCallback(async (item: KnowledgeMediaAssetRecord) => {
    if (!selectedBase) return;
    setDeletingMediaAssetId(item.id);
    try {
      await deleteKnowledgeMediaAsset(selectedBase.id, item.id);
      message.success('配套素材已移除');
      await loadMediaAssets();
    } finally {
      setDeletingMediaAssetId(null);
    }
  }, [loadMediaAssets, selectedBase]);

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
      const modeLabel = recallModeText[result.mode] || '无命中';
      setRecallChunks(result.chunks);
      setRecallMediaAssets(result.mediaAssets || []);
      setRecallMode(modeLabel);
      setRecallModeKey(result.mode);
      setRecallSkipReason(result.skipReason || '');
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


  const documentColumns = useMemo<ColumnsType<KnowledgeDocumentRecord>>(() => [
    {
      title: '文档',
      key: 'document',
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{item.title}</Typography.Text>
          <Typography.Text className="!text-xs font-mono !text-slate-500 bg-slate-50 border border-slate-100 px-1 py-0.5 rounded">{item.fileName}</Typography.Text>
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
      render: (value: number | null) => <span className="font-mono text-xs">{formatFileSize(value)}</span>,
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
      render: (value: number) => <span className="font-mono text-xs">{value}</span>,
    },
    {
      title: '索引',
      key: 'indexingStatus',
      width: 150,
      render: (_, item) => (
        <Space direction="vertical" size={2}>
          <Tag color={indexStatusColor[item.indexingStatus]}>{item.indexingStatusLabel || item.indexingStatus}</Tag>
          <Typography.Text className="!text-xs !text-slate-500"><span className="font-mono font-semibold">{item.chunkCount}</span> 块</Typography.Text>
          {item.indexingStatus === 'failed' && item.indexingError ? (
            <Typography.Text className="!max-w-[180px] !text-xs" type="danger" ellipsis={{ tooltip: item.indexingError }}>
              {item.indexingError}
            </Typography.Text>
          ) : null}
        </Space>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      render: (value: string) => <span className="font-mono text-xs text-slate-500">{value}</span>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      align: 'right',
      render: (_, item) => (
        <div className="flex items-center justify-end gap-3.5">
          <Button
            type="link"
            className="!p-0 !h-auto text-teal-600 hover:text-teal-700 font-semibold"
            disabled={!canDownload}
            loading={downloadLoadingId === item.id}
            onClick={() => void handleSingleDownload(item)}
          >
            下载
          </Button>
          <Button
            type="link"
            className="!p-0 !h-auto text-teal-600 hover:text-teal-700 font-semibold"
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
            <Button
              type="link"
              danger
              className="!p-0 !h-auto font-semibold"
              disabled={!canDelete}
              loading={deletingDocumentId === item.id}
            >
              删除
            </Button>
          </Popconfirm>
        </div>
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

  const resourceColumns = useMemo<ColumnsType<ResourceRecord>>(() => [
    {
      title: '资源',
      key: 'resource',
      render: (_, item) => (
        <Space size={10}>
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-100 border border-slate-200/60 text-slate-500">
            {item.resourceType === 'image' ? <IconPhoto size={18} /> : <IconVideo size={18} />}
          </div>
          <Space direction="vertical" size={2}>
            <Typography.Text strong className="!text-sm text-slate-800">{item.name}</Typography.Text>
            <Typography.Text className="!text-xs !text-slate-500">{item.resourceTypeLabel} <span className="mx-1 text-slate-300">·</span> {item.categoryLabel}</Typography.Text>
          </Space>
        </Space>
      ),
    },
    {
      title: '说明',
      dataIndex: 'description',
      render: (value: string) => (
        <Typography.Text className="!text-sm !text-slate-600" ellipsis={{ tooltip: value }}>
          {value || '--'}
        </Typography.Text>
      ),
    },
  ], []);

  const editBaseModal = (
    <Modal
      title={<span className="text-slate-800 font-bold">编辑知识库配置</span>}
      open={editOpen}
      width={640}
      confirmLoading={editSaving}
      onOk={() => void handleEditBase()}
      onCancel={() => {
        setEditOpen(false);
        setEditingBase(null);
      }}
      okText="保存更改"
      cancelText="取消"
      className="top-[10%]"
    >
      <Form form={editForm} layout="vertical" className="mt-4">
        <div className="space-y-6">
          <section>
            <div className="mb-3 text-sm font-semibold text-slate-800 border-b border-slate-100 pb-2">基本信息</div>
            <Form.Item name="name" label={<span className="text-slate-600">名称</span>} rules={[{ required: true, message: '请输入知识库名称' }]}>
              <Input maxLength={128} className="rounded-md" />
            </Form.Item>
            <Form.Item name="description" label={<span className="text-slate-600">说明</span>} className="!mb-0">
              <Input.TextArea maxLength={255} rows={3} placeholder="说明资料范围、维护责任人或适用业务场景" className="rounded-md" />
            </Form.Item>
          </section>

          <section>
            <div className="mb-3 text-sm font-semibold text-slate-800 border-b border-slate-100 pb-2">检索与分块策略</div>
            <div className="mb-4 rounded-md bg-slate-50/50 p-3 border border-slate-100 text-[13px] text-slate-500 leading-relaxed">
              <IconStack2 size={14} className="inline mr-1 text-slate-400" />
              分块长度决定召回颗粒度，较大的分块能保留完整语义，但消耗更多 Token。重叠区能防止关键信息在边界截断。
            </div>
            
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <Form.Item name="chunkSize" label={<span className="text-slate-600">分块长度 (Chunk Size)</span>} rules={[{ required: true, message: '请输入分块长度' }]}>
                <InputNumber min={100} max={4000} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
              <Form.Item
                name="chunkOverlap"
                label={<span className="text-slate-600">分块重叠 (Overlap)</span>}
                dependencies={['chunkSize']}
                rules={[
                  { required: true, message: '请输入分块重叠' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      const chunkSize = Number(getFieldValue('chunkSize') || defaultIndexConfig.chunkSize);
                      if (Number(value || 0) >= chunkSize) {
                        return Promise.reject(new Error('重叠必须小于分块长度'));
                      }
                      return Promise.resolve();
                    },
                  }),
                ]}
              >
                <InputNumber min={0} max={1000} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
              <Form.Item name="retrievalTopN" label={<span className="text-slate-600">文本召回段数 (Top N)</span>} rules={[{ required: true, message: '请输入文本召回段数' }]}>
                <InputNumber min={1} max={20} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
              <Form.Item name="retrievalMinScore" label={<span className="text-slate-600">最低相关度阈值</span>} rules={[{ required: true, message: '请输入最低相关度' }]}> 
                <InputNumber min={0} max={1} step={0.05} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
            </div>
          </section>

          <section>
            <div className="mb-3 text-sm font-semibold text-slate-800 border-b border-slate-100 pb-2">配套素材召回配置</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <Form.Item name="mediaMaxAssets" label={<span className="text-slate-600">素材召回上限</span>} tooltip="0 表示不限制，有几张命中就返回几张。" rules={[{ required: true, message: '请输入素材召回上限' }]}> 
                <InputNumber min={0} max={200} precision={0} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
              <Form.Item name="mediaMinRelevance" label={<span className="text-slate-600">素材最低相关度</span>} rules={[{ required: true, message: '请输入素材最低相关度' }]}> 
                <InputNumber min={0} max={1} step={0.05} className="!w-full rounded-md font-mono text-sm" />
              </Form.Item>
            </div>
          </section>
        </div>
      </Form>
    </Modal>
  );

  const documentManagementTab = (
    <Space direction="vertical" size={16} className="w-full">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={16} className="w-full">
            <div className="flex flex-col gap-4">
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
                className="!w-full !border-dashed !border-slate-200 hover:!border-teal-400 !bg-slate-50/50 hover:!bg-teal-50/10 !transition-colors !rounded-xl"
              >
                <div className="py-4">
                  <p className="ant-upload-drag-icon !mb-2 !text-teal-600"><IconCloudUpload className="text-2xl" /></p>
                  <p className="ant-upload-text !text-sm !font-medium !text-slate-700">拖拽文件到此处，或 <span className="text-teal-600">点击上传</span></p>
                  <p className="ant-upload-hint !text-xs !text-slate-400 mt-1">支持并发上传最多 3 个文件。支持格式：{KNOWLEDGE_BASE_ACCEPT.replace(/\./g, '').toUpperCase()}</p>
                </div>
              </Upload.Dragger>
            </div>

            {uploadTasks.length > 0 && (
              <div className="space-y-3 mt-2">
                {uploadTasks.map((task) => (
                  <div key={task.id} className="rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-3 transition-all">
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <Typography.Text className="!text-sm font-medium !text-slate-700 truncate max-w-[280px]" title={task.file.name}>{task.file.name}</Typography.Text>
                      <Tag color={task.status === 'success' ? 'success' : task.status === 'error' ? 'error' : 'processing'}>
                        {task.status === 'pending' && '等待上传'}
                        {task.status === 'uploading' && '上传中'}
                        {task.status === 'success' && '上传成功'}
                        {task.status === 'error' && '上传失败'}
                      </Tag>
                    </div>
                    <Progress percent={task.progress} size="small" status={task.status === 'error' ? 'exception' : undefined} strokeColor="#14b8a6" className="mt-2" />
                    {task.error ? <Typography.Text className="!text-xs !text-red-500 block mt-1">{task.error}</Typography.Text> : null}
                  </div>
                ))}
              </div>
            )}
          </Space>
        </Card>

        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Space direction="vertical" size={16} className="w-full">
            <Typography.Title level={5} className="!mb-0">索引流程</Typography.Title>
            <div className="relative pl-6 space-y-4 before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-100">
              {detailWorkflow.map((item, index) => (
                <div key={item.title} className="relative flex gap-3">
                  <div className="absolute -left-[22px] top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-white border-2 border-teal-500 z-10">
                    <div className="h-1.5 w-1.5 rounded-full bg-teal-500" />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-teal-600 text-xs font-semibold font-mono">STEP 0{index + 1}</span>
                      <Typography.Text strong className="!text-sm !text-slate-900">{item.title}</Typography.Text>
                    </div>
                    <Typography.Paragraph className="!mb-0 !mt-1 !text-xs !text-slate-500">{item.description}</Typography.Paragraph>
                  </div>
                </div>
              ))}
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
          scroll={{ x: 900 }}
        />
      </Card>
    </Space>
  );

  const mediaManagementTab = (
    <Space direction="vertical" size={18} className="w-full">
      <section className="rounded-xl border border-slate-200/70 bg-white p-5 md:p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-w-0 flex-col justify-between gap-6">
            <div>
              <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-teal-100 bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-700">
                <IconPhoto size={14} />
                多模态素材增强
              </div>
              <Typography.Title level={4} className="!mb-2 !text-slate-900 !font-semibold">配套素材工作台</Typography.Title>
              <Typography.Paragraph className="!mb-0 max-w-2xl !text-[13px] !leading-relaxed !text-slate-500">
                把图片、视频等资料放进召回链路。素材可补充场景画面和操作示意，智能体将按相关度在回答中一并返回。
              </Typography.Paragraph>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">绑定素材</div>
                <div className="mt-1 font-mono text-xl font-semibold text-slate-800">{mediaAssetStats.total}</div>
              </div>
              <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">可召回</div>
                <div className="mt-1 font-mono text-xl font-semibold text-teal-600">{mediaAssetStats.enabled}</div>
              </div>
              <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">索引就绪</div>
                <div className="mt-1 font-mono text-xl font-semibold text-teal-600">{mediaAssetStats.ready}</div>
              </div>
              <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">图片 / 视频</div>
                <div className="mt-1 font-mono text-xl font-semibold text-slate-800">{mediaAssetStats.images}<span className="text-sm text-slate-400 font-normal mx-1">/</span>{mediaAssetStats.videos}</div>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200/60 bg-slate-50/50 p-4 flex flex-col justify-between">
            <div>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400 font-mono">RECALL POLICY</div>
                  <div className="mt-0.5 text-[13px] font-semibold text-slate-800">素材召回配置</div>
                </div>
                <div className="rounded bg-white border border-slate-200 p-1.5 text-slate-400 shadow-sm">
                  <IconAdjustments size={16} />
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between rounded-md bg-white border border-slate-100 px-3 py-2">
                  <span className="text-xs text-slate-500">返回上限</span>
                  <span className="font-mono text-sm font-semibold text-slate-800">{selectedBase?.mediaMaxAssets || '不限'}</span>
                </div>
                <div className="flex items-center justify-between rounded-md bg-white border border-slate-100 px-3 py-2">
                  <span className="text-xs text-slate-500">最低相关度</span>
                  <span className="font-mono text-sm font-semibold text-slate-800">{selectedBase?.mediaMinRelevance ?? defaultIndexConfig.mediaMinRelevance}</span>
                </div>
              </div>
            </div>
            <div className="mt-5 flex items-center gap-2">
              <Button className="!flex-1 !text-[13px]" icon={<IconRefresh size={16} />} onClick={() => void loadMediaAssets()}>刷新</Button>
              <Button className="!flex-1 !text-[13px]" type="primary" icon={<IconPlus size={16} />} disabled={!canUpload} onClick={() => void openBindMediaModal()}>
                绑定素材
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Spin spinning={mediaAssetsLoading}>
        {mediaAssets.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {mediaAssets.map((item) => {
              const isImage = item.resourceType === 'image';
              return (
                <Card
                  key={item.id}
                  variant="borderless"
                  className="group !overflow-hidden !rounded-xl !border !border-slate-200/70 !shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all hover:!border-teal-300/50 hover:!shadow-[0_4px_10px_rgba(15,23,42,0.06)] [&_.ant-card-body]:!p-0 bg-white"
                >
                  <div className="flex flex-col sm:flex-row h-full">
                    <div className="relative flex min-h-[160px] items-center justify-center overflow-hidden border-b sm:border-b-0 sm:border-r border-slate-100 bg-slate-50 sm:w-44 shrink-0">
                      {item.url && !item.isMissing ? (
                        isImage ? (
                          <img src={item.url} alt={item.resourceName || '素材预览'} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
                        ) : (
                          <video src={item.url} className="h-full w-full object-cover" muted preload="metadata" />
                        )
                      ) : (
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 text-slate-400 border border-slate-200/60">
                          {isImage ? <IconPhoto size={24} /> : <IconVideo size={24} />}
                        </div>
                      )}
                      <div className="absolute left-2.5 top-2.5 flex gap-1.5">
                        <span className="inline-flex items-center gap-1 rounded bg-slate-900/70 px-1.5 py-0.5 text-[10px] font-medium text-white backdrop-blur border border-white/10">
                          {isImage ? <IconPhoto size={10} /> : <IconVideo size={10} />}
                          {item.resourceTypeLabel}
                        </span>
                      </div>
                      <div className="absolute bottom-2.5 left-2.5 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-700 shadow-sm backdrop-blur border border-slate-200/60">
                        P{item.priority}
                      </div>
                    </div>
                    
                    <div className="flex min-w-0 flex-1 flex-col justify-between p-4">
                      <div>
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <Typography.Title level={5} className="!mb-1.5 !truncate !text-sm !font-semibold !text-slate-800" title={item.resourceName || '素材已删除'}>
                              {item.resourceName || '素材已删除'}
                            </Typography.Title>
                            <div className="flex flex-wrap gap-1.5">
                              <Tag color={item.isMissing ? 'error' : item.isEnabled ? 'success' : 'default'} className="!m-0 !border-none !bg-slate-100 !text-slate-600">
                                {item.isMissing ? (
                                  <span className="text-red-600">已删除</span>
                                ) : item.isEnabled ? (
                                  <span className="text-teal-700 font-medium">● 启用</span>
                                ) : '暂停'}
                              </Tag>
                              <Tag color="default" className={`!m-0 !border-none ${item.embeddingStatus === 'ready' ? '!bg-teal-50 !text-teal-700' : item.embeddingStatus === 'failed' ? '!bg-red-50 !text-red-600' : '!bg-slate-100 !text-slate-600'}`}>
                                {item.embeddingStatusLabel || item.embeddingStatus || '待处理'}
                              </Tag>
                            </div>
                          </div>
                        </div>
                        <Typography.Paragraph className="!mb-2.5 !text-[13px] !leading-relaxed !text-slate-500" ellipsis={{ rows: 2, tooltip: item.description || item.vlmDescription }}>
                          {item.description || item.vlmDescription || '暂无说明，建议补充说明此素材适用的场景。'}
                        </Typography.Paragraph>
                        
                        <div className="min-h-[24px]">
                          {item.keywords ? (
                            <div className="flex flex-wrap gap-1.5">
                              {item.keywords.split(/[，,\s]+/).filter(Boolean).slice(0, 4).map((keyword) => (
                                <span key={keyword} className="rounded bg-slate-50 border border-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">#{keyword}</span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-400">缺少关键词</span>
                          )}
                        </div>
                        {item.embeddingStatus === 'failed' && item.embeddingError ? (
                          <Typography.Text className="!mt-1 block !text-[11px]" type="danger" ellipsis={{ tooltip: item.embeddingError }}>
                            {item.embeddingError}
                          </Typography.Text>
                        ) : null}
                      </div>
                      
                      <div className="mt-3 flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
                        <Typography.Text className="!max-w-[140px] !text-[10px] !text-slate-400 font-mono" ellipsis={{ tooltip: item.embeddingModel }}>
                          {item.embeddingModel || '--'}
                        </Typography.Text>
                        <Space size={14}>
                          <button type="button" className="text-[13px] font-medium text-slate-500 hover:text-teal-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled={!canUpload} onClick={() => openEditMediaAsset(item)}>
                            编辑
                          </button>
                          <Popconfirm
                            title={<span className="text-sm font-medium">移除配套素材</span>}
                            description={<span className="text-[13px] text-slate-500 block mt-1">确认从知识库中移除此素材吗？</span>}
                            okText="移除"
                            cancelText="取消"
                            okButtonProps={{ danger: true, size: 'small', loading: deletingMediaAssetId === item.id }}
                            cancelButtonProps={{ size: 'small' }}
                            disabled={!canUpload}
                            placement="topRight"
                            onConfirm={() => void handleDeleteMediaAsset(item)}
                          >
                            <button type="button" className="text-[13px] font-medium text-slate-500 hover:text-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled={!canUpload || deletingMediaAssetId === item.id}>
                              移除
                            </button>
                          </Popconfirm>
                        </Space>
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <Card variant="borderless" className="!rounded-xl !border !border-dashed !border-slate-300 !bg-slate-50/50 !shadow-none py-8">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={(
                <div className="space-y-1.5">
                  <div className="font-medium text-slate-700 text-sm">尚未绑定素材</div>
                  <div className="text-[13px] text-slate-500 max-w-sm mx-auto">绑定素材并补充说明，智能体回答时可附带相关视觉内容。</div>
                </div>
              )}
            >
              <Button type="primary" icon={<IconPlus size={16} />} className="mt-2" disabled={!canUpload} onClick={() => void openBindMediaModal()}>
                绑定第一批素材
              </Button>
            </Empty>
          </Card>
        )}
      </Spin>
    </Space>
  );

  const mediaAssetModals = (
    <>
      <Modal
        title={<span className="text-slate-800 font-bold">绑定配套素材</span>}
        open={bindMediaOpen}
        width={720}
        confirmLoading={bindingMedia}
        onOk={() => void handleBindMediaAssets()}
        onCancel={() => {
          setBindMediaOpen(false);
          setSelectedResourceKeys([]);
        }}
        okText={`确认绑定 ${selectedResourceKeys.length ? `(${selectedResourceKeys.length})` : ''}`}
        cancelText="取消"
        className="top-[10%]"
      >
        <div className="mt-2 text-[13px] text-slate-500 mb-4 border-b border-slate-100 pb-3">
          从资源库中选择图片或视频绑定到当前知识库。选中后，系统将自动进行多模态向量化。
        </div>
        <Table
          rowKey="id"
          loading={bindableResourcesLoading}
          columns={resourceColumns}
          dataSource={bindableResources}
          rowSelection={{ selectedRowKeys: selectedResourceKeys, onChange: setSelectedResourceKeys }}
          pagination={{ pageSize: 6, showSizeChanger: false }}
          locale={{ emptyText: '资源库里没有可绑定的素材' }}
          scroll={{ y: 360 }}
          size="small"
        />
      </Modal>

      <Modal
        title={<span className="text-slate-800 font-bold">编辑素材信息</span>}
        open={Boolean(editingMediaAsset)}
        width={520}
        confirmLoading={mediaAssetSaving}
        onOk={() => void handleSaveMediaAsset()}
        onCancel={() => setEditingMediaAsset(null)}
        okText="保存更改"
        cancelText="取消"
      >
        <Form form={mediaAssetForm} layout="vertical" className="mt-4">
          {editingMediaAsset?.vlmDescription ? (
            <div className="mb-5 rounded-md border border-teal-100 bg-teal-50/50 p-3">
              <div className="text-xs font-semibold text-teal-800 mb-1 flex items-center gap-1.5">
                <IconPhoto size={14} /> AI 基础描述
              </div>
              <div className="text-[13px] leading-relaxed text-teal-700">
                {editingMediaAsset.vlmDescription}
              </div>
            </div>
          ) : null}
          <Form.Item name="keywords" label={<span className="text-slate-600 text-[13px]">匹配关键词</span>} extra={<span className="text-[11px]">空格或逗号分隔。关键词命中可提升召回权重。</span>}>
            <Input.TextArea rows={2} maxLength={255} placeholder="例如：展厅 导览 路线 入口" className="rounded-md" />
          </Form.Item>
          <Form.Item name="description" label={<span className="text-slate-600 text-[13px]">素材说明</span>} extra={<span className="text-[11px]">说明该素材适合回答的问题场景。</span>}>
            <Input.TextArea rows={3} maxLength={500} placeholder="例如：当用户询问如何前往展厅时，出示此平面图。" className="rounded-md" />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4 mt-4 border-t border-slate-100 pt-4">
            <Form.Item name="priority" label={<span className="text-slate-600 text-[13px]">召回优先级</span>} initialValue={0} className="!mb-0" extra={<span className="text-[11px]">数值越小越优先 (默认 0)</span>}>
              <InputNumber min={0} max={999} className="!w-full rounded-md font-mono" />
            </Form.Item>
            <Form.Item name="isEnabled" label={<span className="text-slate-600 text-[13px]">状态</span>} valuePropName="checked" initialValue className="!mb-0">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </>
  );

  const recallTestTab = (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={16} className="w-full">
          <div className="flex items-center gap-2">
            <IconFileSearch className="text-teal-600 text-lg" />
            <Typography.Title level={5} className="!mb-0">召回测试</Typography.Title>
          </div>
          <Typography.Text className="!text-sm !text-slate-500">先用真实业务问题验证命中片段，再绑定给智能体。</Typography.Text>
          <Input.TextArea rows={5} value={recallQuery} onChange={(event) => setRecallQuery(event.target.value)} placeholder="输入问题，例如：设备离线后客户应该如何处理？" />
          <div className="flex items-center justify-between gap-3">
            <Space>
              <Typography.Text className="!text-sm !text-slate-500">Top N</Typography.Text>
              <InputNumber min={1} max={20} value={recallTopN} onChange={(value) => setRecallTopN(Number(value || 5))} />
            </Space>
            <Button type="primary" icon={<IconCloudUpload />} loading={recallLoading} onClick={() => void handleRecallTest()}>测试召回</Button>
          </div>
          {recallMode ? (
            <Space direction="vertical" size={6} className="w-full">
              <Tag color={recallModeColor[recallModeKey] || 'default'} className="w-fit">
                {recallMode}
              </Tag>
              {recallSkipReason ? (
                <Typography.Text className="!text-xs !text-amber-700">
                  {skipReasonText[recallSkipReason] || recallSkipReason}
                </Typography.Text>
              ) : null}
            </Space>
          ) : null}
          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <Typography.Text strong className="!text-sm !text-slate-800">最近测试</Typography.Text>
            <div className="mt-3 space-y-2 max-h-[220px] overflow-y-auto custom-scrollbar">
              {recallHistory.length > 0 ? recallHistory.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="w-full rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-left text-sm transition hover:border-teal-200 hover:bg-teal-50/30"
                  onClick={() => setRecallQuery(item.query)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-slate-700">{item.query}</span>
                    <span className="text-xs font-mono bg-slate-50 border border-slate-100 text-slate-500 px-1.5 py-0.5 rounded shrink-0">{item.count} 条</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{item.mode}</div>
                </button>
              )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无测试历史" />}
            </div>
          </div>
        </Space>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Space direction="vertical" size={16} className="w-full">
          <Typography.Title level={5} className="!mb-0">命中片段</Typography.Title>
          <div className="max-h-[560px] overflow-y-auto pr-1 custom-scrollbar">
            {recallMediaAssets.length > 0 ? (
              <div className="mb-4 rounded-xl border border-cyan-100 bg-cyan-50/40 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <IconPhoto size={16} className="text-cyan-600" />
                  <Typography.Text strong className="!text-sm !text-cyan-800">命中素材</Typography.Text>
                </div>
                <div className="grid grid-cols-1 gap-2">
                  {recallMediaAssets.map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-3 rounded-lg border border-white/70 bg-white px-3 py-2">
                      <Space size={8}>
                        <span className={`flex h-7 w-7 items-center justify-center rounded-md ${item.resourceType === 'image' ? 'bg-cyan-50 text-cyan-600' : 'bg-violet-50 text-violet-600'}`}>
                          {item.resourceType === 'image' ? <IconPhoto size={15} /> : <IconVideo size={15} />}
                        </span>
                        <div>
                          <Typography.Text strong className="!text-sm !text-slate-800">{item.resourceName}</Typography.Text>
                          <Typography.Paragraph className="!mb-0 !text-xs !text-slate-500" ellipsis={{ rows: 1, tooltip: item.description || item.keywords }}>
                            {item.description || item.keywords || '--'}
                          </Typography.Paragraph>
                        </div>
                      </Space>
                      <Tag color="cyan" className="!font-mono shrink-0">
                        相关度 {Math.round((item.relevance ?? 0) * 100)}%
                      </Tag>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {recallChunks.length > 0 ? (
              <Space direction="vertical" size={10} className="w-full">
                {recallChunks.map((chunk, index) => (
                  <div key={`${chunk.documentId}-${chunk.chunkIndex}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4 hover:border-teal-100 hover:bg-teal-50/5 transition-all">
                    <div className="mb-2.5 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Typography.Text strong className="!text-sm !text-slate-800">{chunk.documentTitle}</Typography.Text>
                        {chunk.chunkIndex !== null && (
                          <span className="text-xs font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200/40">
                            #{chunk.chunkIndex}
                          </span>
                        )}
                      </div>
                      <Tag color="success" className="!font-mono !border-emerald-100 !bg-emerald-50 !text-emerald-700">
                        score {chunk.score.toFixed(4)}
                      </Tag>
                    </div>
                    <Typography.Paragraph className="!mb-0 !text-sm !text-slate-600 !leading-relaxed">{chunk.content}</Typography.Paragraph>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={recallModeKey === 'skipped' ? '这个问题没有进入知识库检索' : '暂无召回结果'}
              />
            )}
          </div>
        </Space>
      </Card>
    </div>
  );

  if (!selectedBase) {
    return (
      <Space direction="vertical" size={20} className="w-full">
        {/* Hero Section */}
        <section className="space-y-3 relative overflow-hidden rounded-2xl p-5 sm:p-6 md:p-8 bg-gradient-to-br from-teal-600/5 to-teal-500/5 border border-teal-600/10">
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-teal-50 text-teal-700 rounded-full mb-4 border border-teal-100">
              <IconShieldCheck className="text-[14px]" />
              <span className="text-xs font-semibold">企业知识沉淀与智能体召回中心</span>
            </div>
            <Typography.Title level={2} className="!mb-2 !text-slate-900">知识库</Typography.Title>
            <p className="text-sm text-slate-500 max-w-3xl leading-relaxed !mb-0">
              这里把“创建资料集”、“导入文档”、“验证召回”、“绑定智能体”收敛到一个页面，先把资料整理成可验证的知识资产，再提供给智能体使用。
            </p>
          </div>
          <div className="absolute right-0 top-0 w-1/3 h-full opacity-[0.03] pointer-events-none flex items-center justify-end pr-8">
            <IconFlask className="text-[180px] rotate-12 text-teal-800" />
          </div>
        </section>

        {/* Summary Cards Row */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200/60 shadow-[0px_4px_20px_rgba(0,0,0,0.015)] hover:shadow-md hover:border-slate-300/60 transition-all duration-300 flex items-center justify-between h-24">
            <div className="flex flex-col justify-between h-full py-0.5">
              <span className="text-xs text-slate-400 font-medium">知识库总数</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono text-slate-800">{baseTotal}</span>
                <span className="text-[10px] text-teal-600/70 font-semibold bg-teal-50 px-1.5 py-0.5 rounded-full border border-teal-100/30">本月新建</span>
              </div>
            </div>
            <div className="p-2.5 bg-slate-100 text-teal-600 rounded-xl shrink-0">
              <IconDatabase size={20} />
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-slate-200/60 shadow-[0px_4px_20px_rgba(0,0,0,0.015)] hover:shadow-md hover:border-slate-300/60 transition-all duration-300 flex items-center justify-between h-24">
            <div className="flex flex-col justify-between h-full py-0.5">
              <span className="text-xs text-slate-400 font-medium">活动知识库</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono text-slate-800">{activeBaseCount}</span>
                <span className="text-[10px] text-emerald-600/70 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded-full border border-emerald-100/30">100% 运行中</span>
              </div>
            </div>
            <div className="p-2.5 bg-slate-100 text-teal-600 rounded-xl shrink-0">
              <IconShieldCheck size={20} />
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-slate-200/60 shadow-[0px_4px_20px_rgba(0,0,0,0.015)] hover:shadow-md hover:border-slate-300/60 transition-all duration-300 flex items-center justify-between h-24">
            <div className="flex flex-col justify-between h-full py-0.5">
              <span className="text-xs text-slate-400 font-medium">包含文档数</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono text-slate-800">{visibleDocumentCount}</span>
                <span className="text-[10px] text-slate-500 font-semibold bg-slate-50 px-1.5 py-0.5 rounded-full border border-slate-200/40">已入库</span>
              </div>
            </div>
            <div className="p-2.5 bg-slate-100 text-slate-500 rounded-xl shrink-0">
              <IconFilePlus size={20} />
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-slate-200/60 shadow-[0px_4px_20px_rgba(0,0,0,0.015)] hover:shadow-md hover:border-slate-300/60 transition-all duration-300 flex items-center justify-between h-24">
            <div className="flex flex-col justify-between h-full py-0.5">
              <span className="text-xs text-slate-400 font-medium">最近更新</span>
              <div className="flex flex-col mt-1">
                <span className="text-sm font-semibold font-mono text-slate-700 leading-tight">{latestUpdatedAt ? latestUpdatedAt.split(' ')[0] : '--'}</span>
                <span className="text-[10px] text-slate-400 font-mono mt-0.5">{latestUpdatedAt ? latestUpdatedAt.split(' ')[1] : ''}</span>
              </div>
            </div>
            <div className="p-2.5 bg-slate-100 text-slate-500 rounded-xl shrink-0">
              <IconRefresh size={20} />
            </div>
          </div>
        </section>

        {/* Main Grid Layout */}
        <section className="grid grid-cols-1 gap-5 xl:grid-cols-12 items-start">
          {/* Left Column: Knowledge Base List */}
          <div className="col-span-12 xl:col-span-9">
            <Card variant="borderless" className="!rounded-xl !border !border-slate-100 !shadow-[0px_4px_20px_rgba(0,0,0,0.02)] overflow-hidden [&_.ant-card-body]:!p-0">
              {/* Toolbar */}
              <div className="p-4 border-b border-slate-100/80 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between bg-slate-50/50">
                <div className="flex items-center gap-3">
                  <Input.Search
                    allowClear
                    placeholder="搜索知识库"
                    className="!w-44 sm:!w-52 md:!w-64"
                    onSearch={(value) => {
                      setBaseKeyword(value.trim());
                      setBasePage(1);
                    }}
                  />
                  <Button icon={<IconRefresh />} onClick={() => void loadBases()}>刷新</Button>
                </div>
                <Button type="primary" icon={<IconPlus />} disabled={!canUpload} onClick={() => setCreateOpen(true)}>
                  创建知识库
                </Button>
              </div>

              {/* Card List / Grid */}
              <Spin spinning={baseLoading}>
                <div className="p-4 sm:p-5">
                  {bases.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4">
                      {bases.map((item) => {
                        // Select icon based on keywords in name
                        let cardIcon = <IconDatabase />;
                        const name = item.name;
                        if (name.includes('医') || name.includes('健康') || name.includes('药')) {
                          cardIcon = <IconShieldCheck />;
                        } else if (name.includes('科') || name.includes('数') || name.includes('网') || name.includes('算') || name.includes('智能') || name.includes('系统')) {
                          cardIcon = <IconStack2 />;
                        } else if (name.includes('城') || name.includes('游') || name.includes('古') || name.includes('馆') || name.includes('历史') || name.includes('景')) {
                          cardIcon = <IconCompass />;
                        } else if (name.includes('文档') || name.includes('书') || name.includes('学') || name.includes('策略') || name.includes('政策')) {
                          cardIcon = <IconBook />;
                        } else if (name.includes('客服') || name.includes('服务') || name.includes('售后')) {
                          cardIcon = <IconFlask />;
                        }

                        const iconBg = item.isActive
                          ? 'bg-teal-50 text-teal-600'
                          : 'bg-slate-100 text-slate-500';

                        return (
                          <div
                            key={item.id}
                            className="bg-white rounded-xl border border-slate-200/60 hover:border-teal-500/30 p-4 sm:p-5 shadow-[0px_4px_20px_rgba(0,0,0,0.015)] hover:shadow-[0px_8px_30px_rgba(20,184,166,0.06)] hover:-translate-y-0.5 transition-all duration-300 flex flex-col justify-between group"
                          >
                            <div>
                              {/* Header Row */}
                              <div className="flex items-start justify-between gap-2 mb-4">
                                <div className={`p-2.5 rounded-xl ${iconBg} shrink-0 shadow-sm transition-transform group-hover:scale-105 duration-300`}>
                                  {React.cloneElement(cardIcon as React.ReactElement, { size: 20 })}
                                </div>
                                <div className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-medium font-sans ${item.isActive ? 'bg-emerald-50/70 border-emerald-100 text-emerald-700' : 'bg-slate-50 border-slate-200/60 text-slate-500'}`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${item.isActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
                                  {item.isActive ? '启用' : '停用'}
                                </div>
                              </div>

                              {/* Title & Description */}
                              <h4 className="text-sm sm:text-base font-bold text-slate-800 line-clamp-1 mb-1 group-hover:text-teal-600 transition-colors duration-200" title={item.name}>
                                {item.name}
                              </h4>
                              <p className="text-xs sm:text-sm text-slate-400 line-clamp-2 mb-4 leading-relaxed" title={item.description || '暂无描述'}>
                                {item.description || '暂无描述'}
                              </p>
                            </div>

                            <div>
                              {/* Stats & Meta */}
                              <div className="grid grid-cols-2 gap-4 py-3.5 border-y border-slate-100/80">
                                <div>
                                  <span className="text-xs font-bold font-mono text-slate-400 uppercase tracking-wider block">包含文档</span>
                                  <span className="text-sm font-semibold text-slate-700 font-mono mt-0.5 inline-block">
                                    {item.documentCount} <span className="font-sans font-normal text-xs text-slate-400">份</span>
                                  </span>
                                </div>
                                <div>
                                  <span className="text-xs font-bold font-mono text-slate-400 uppercase tracking-wider block">分块配置</span>
                                  <span className="text-sm font-semibold text-slate-700 font-mono mt-0.5 inline-block">
                                    {item.chunkSize}/{item.chunkOverlap}
                                  </span>
                                </div>
                              </div>
                              <div className="flex items-center justify-between text-xs text-slate-400 mt-2 font-mono">
                                <span>更新时间</span>
                                <span>{item.updated_at}</span>
                              </div>

                              {/* Actions Footer */}
                              <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100">
                                <div className="flex gap-1">
                                  <Button
                                    type="text"
                                    size="small"
                                    className="text-slate-400 hover:text-teal-600 hover:bg-teal-50/50 rounded-lg flex items-center justify-center p-1.5"
                                    icon={<IconPencil className="text-xs" />}
                                    disabled={!canUpload}
                                    onClick={() => openEditBase(item)}
                                  />
                                  <Popconfirm
                                    title="删除知识库"
                                    description={`确认删除“${item.name}”及其文档吗？`}
                                    okText="删除"
                                    cancelText="取消"
                                    okButtonProps={{ danger: true, loading: deletingBaseId === item.id }}
                                    disabled={!canDelete}
                                    onConfirm={() => void handleDeleteBase(item)}
                                  >
                                    <Button
                                      type="text"
                                      size="small"
                                      danger
                                      className="text-slate-400 hover:text-red-600 hover:bg-red-50/50 rounded-lg flex items-center justify-center p-1.5"
                                       icon={<IconTrash className="text-xs" />}
                                      disabled={!canDelete}
                                      loading={deletingBaseId === item.id}
                                    />
                                  </Popconfirm>
                                </div>
                                
                                <Button
                                  type="primary"
                                  size="small"
                                  className="!bg-teal-600 hover:!bg-teal-700 !text-white border-none font-medium rounded-lg px-3 py-1.5 text-xs shadow-sm hover:shadow transition-all duration-200 flex items-center gap-1 group/btn"
                                  onClick={() => setSelectedBase(item)}
                                >
                                  进入管理
                                   <IconArrowRight className="text-[10px] group-hover/btn:translate-x-0.5 transition-transform duration-200" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={baseKeyword ? '没有匹配的知识库' : '还没有知识库，先创建一个用于沉淀业务资料'}
                    />
                  )}
                </div>
              </Spin>

              {/* Pagination */}
              {bases.length > 0 && (
                <div className="p-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/30">
                  <span className="text-xs text-slate-400 font-medium">
                    共 <span className="font-mono text-slate-600 font-semibold">{baseTotal}</span> 个知识库
                  </span>
                  <Pagination
                    current={basePage}
                    pageSize={PAGE_SIZE}
                    total={baseTotal}
                    showSizeChanger={false}
                    onChange={setBasePage}
                    size="small"
                  />
                </div>
              )}
            </Card>
          </div>

          {/* Right Column: Recommended Process */}
          <div className="col-span-12 xl:col-span-3">
            <Card variant="borderless" className="!rounded-xl !border border-slate-200/60 !shadow-[0px_4px_20px_rgba(0,0,0,0.015)]">
              <Space direction="vertical" size={20} className="w-full">
                <h3 className="text-sm font-bold text-slate-800 mb-0 flex items-center gap-2">
                  <span className="w-1.5 h-4 bg-teal-600 rounded-sm"></span>
                  推荐流程
                </h3>
                <div className="space-y-6 relative mt-2">
                  {/* Timeline connector */}
                  <div className="absolute left-3.5 top-3 bottom-3 w-0.5 bg-slate-100"></div>
                  
                  {createGuideCards.map((item, index) => (
                    <div key={item.title} className="relative pl-12">
                      <div className={`absolute left-0 top-0.5 w-7 h-7 rounded-lg flex items-center justify-center z-10 ${item.iconBg} ${item.iconColor} transition-all duration-300`}>
                        {React.cloneElement(item.icon as React.ReactElement, { size: 14 })}
                      </div>
                      <div>
                        <span className={`text-[9px] font-bold font-mono tracking-wider px-2 py-0.5 rounded-full ${index === 0 ? 'bg-teal-50 text-teal-600 border border-teal-100/50' : 'bg-slate-100 text-slate-500 border border-slate-200/30'}`}>
                          STEP 0{index + 1}
                        </span>
                        <h4 className="text-xs font-bold text-slate-800 mt-2 mb-1">
                          {item.title}
                        </h4>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          {item.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>


              </Space>
            </Card>
          </div>
        </section>

        {/* Create and Edit Modals */}
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
            <div className="mt-2 mb-4 p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs text-slate-500 leading-relaxed">
              <div className="font-semibold text-slate-600 mb-1">分块参数指南：</div>
              <div>分块长度决定了大模型上下文召回颗粒度。较大的分块能保留更多完整语义，但单次召回消耗的 Token 更多。分块重叠能避免关键信息在切分边界处截断丢失。</div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <Form.Item
                name="chunkSize"
                label="分块长度"
                initialValue={defaultIndexConfig.chunkSize}
                rules={[{ required: true, message: '请输入分块长度' }]}
              >
                <InputNumber min={100} max={4000} className="!w-full" />
              </Form.Item>
              <Form.Item
                name="chunkOverlap"
                label="分块重叠"
                initialValue={defaultIndexConfig.chunkOverlap}
                dependencies={['chunkSize']}
                rules={[
                  { required: true, message: '请输入分块重叠' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      const chunkSize = Number(getFieldValue('chunkSize') || defaultIndexConfig.chunkSize);
                      if (Number(value || 0) >= chunkSize) {
                        return Promise.reject(new Error('重叠必须小于分块长度'));
                      }
                      return Promise.resolve();
                    },
                  }),
                ]}
              >
                <InputNumber min={0} max={1000} className="!w-full" />
              </Form.Item>
              <Form.Item
                name="retrievalTopN"
                label="默认召回段数"
                initialValue={defaultIndexConfig.retrievalTopN}
                rules={[{ required: true, message: '请输入召回段数' }]}
              >
                <InputNumber min={1} max={20} className="!w-full" />
              </Form.Item>
              <Form.Item
                name="retrievalMinScore"
                label="最低相关度"
                initialValue={defaultIndexConfig.retrievalMinScore}
                rules={[{ required: true, message: '请输入最低相关度' }]}
              >
                <InputNumber min={0} max={1} step={0.05} className="!w-full" />
              </Form.Item>
              <Form.Item
                name="mediaMaxAssets"
                label="素材召回上限"
                tooltip="0 表示不限制，有几张命中就返回几张。"
                initialValue={defaultIndexConfig.mediaMaxAssets}
                rules={[{ required: true, message: '请输入素材召回上限' }]}
              >
                <InputNumber min={0} max={200} precision={0} className="!w-full" />
              </Form.Item>
              <Form.Item
                name="mediaMinRelevance"
                label="素材最低相关度"
                initialValue={defaultIndexConfig.mediaMinRelevance}
                rules={[{ required: true, message: '请输入素材最低相关度' }]}
              >
                <InputNumber min={0} max={1} step={0.05} className="!w-full" />
              </Form.Item>
            </div>
          </Form>
        </Modal>

        {editBaseModal}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={20} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-100 !shadow-[0px_4px_20px_rgba(0,0,0,0.02)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <Space size={12} align="start">
            <Button icon={<IconArrowLeft />} onClick={() => setSelectedBase(null)} />
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">{selectedBase.name}</Typography.Title>
              <Typography.Text className="!text-slate-500">{selectedBase.description || '暂无描述'}</Typography.Text>
              <div className="mt-2 flex flex-wrap gap-2">
                <Tag color="cyan" className="!bg-teal-50 !text-teal-700 !border-teal-100">
                  文档 <span className="font-mono font-semibold">{selectedBase.documentCount}</span>
                </Tag>
                <Tag color={selectedBase.isActive ? 'success' : 'default'}>
                  {selectedBase.isActive ? '可用于智能体' : '已停用'}
                </Tag>
                <Tag className="!bg-slate-50 !text-slate-600 !border-slate-200/60">
                  分块 <span className="font-mono font-semibold">{selectedBase.chunkSize}</span> / <span className="font-mono font-semibold">{selectedBase.chunkOverlap}</span>
                </Tag>
                <Tag className="!bg-slate-50 !text-slate-600 !border-slate-200/60">
                  默认召回 <span className="font-mono font-semibold">{selectedBase.retrievalTopN}</span>
                </Tag>
                <Tag className="!bg-slate-50 !text-slate-600 !border-slate-200/60">
                  最低相关度 <span className="font-mono font-semibold">{selectedBase.retrievalMinScore ?? defaultIndexConfig.retrievalMinScore}</span>
                </Tag>
                <Tag className="!bg-slate-50 !text-slate-600 !border-slate-200/60">
                  素材上限 <span className="font-mono font-semibold">{(selectedBase.mediaMaxAssets ?? defaultIndexConfig.mediaMaxAssets) || '不限制'}</span>
                </Tag>
                <Tag className="!bg-slate-50 !text-slate-600 !border-slate-200/60">
                  素材相关度 <span className="font-mono font-semibold">{selectedBase.mediaMinRelevance ?? defaultIndexConfig.mediaMinRelevance}</span>
                </Tag>
              </div>
            </div>
          </Space>
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索标题 / 文件名"
              className="!w-44 sm:!w-52 md:!w-64"
              onSearch={(value) => setDocumentKeyword(value.trim())}
            />
            <Button icon={<IconRefresh />} onClick={() => void loadDocuments()}>刷新</Button>
            <Button
              icon={<IconGitBranch />}
              disabled={!canUpload}
              loading={indexingBase}
              onClick={() => void handleIndexBase()}
            >
              重建索引
            </Button>
            <Button
              type="primary"
              icon={<IconDownload />}
              disabled={!canBulkDownload || selectedRowKeys.length === 0}
              loading={bulkDownloading}
              onClick={() => void handleBulkDownload()}
            >
              批量下载
            </Button>
          </Space>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)]">
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 sm:p-4">
              <div className="text-xs text-slate-500 font-medium">当前文档</div>
              <div className="mt-1 text-xl sm:text-2xl font-semibold text-slate-900 font-mono">
                {selectedBase.documentCount} <span className="text-xs font-normal text-slate-400 font-sans">份</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 sm:p-4">
              <div className="text-xs text-slate-500 font-medium">已选文档</div>
              <div className="mt-1 text-xl sm:text-2xl font-semibold text-slate-900 font-mono">
                {selectedRowKeys.length} <span className="text-xs font-normal text-slate-400 font-sans">份</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 sm:p-4">
              <div className="text-xs text-slate-500 font-medium">召回 Top N</div>
              <div className="mt-1 text-xl sm:text-2xl font-semibold text-slate-900 font-mono">
                {recallTopN} <span className="text-xs font-normal text-slate-400 font-sans">段</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 sm:p-4">
              <div className="text-xs text-slate-500 font-medium">测试记录</div>
              <div className="mt-1 text-xl sm:text-2xl font-semibold text-slate-900 font-mono">
                {recallHistory.length} <span className="text-xs font-normal text-slate-400 font-sans">次</span>
              </div>
            </div>
          </div>
        </Card>
        <Alert
          showIcon
          type="info"
          className="!rounded-xl !border-teal-100 !bg-teal-50/30 !text-teal-800"
          message="上线前建议"
          description="先用真实高频问题完成召回验证，确认片段来源可靠后再绑定到智能体应用。"
        />
      </div>

      <Tabs
        items={[
          { key: 'documents', label: '文档管理', children: documentManagementTab },
          { key: 'media', label: '配套素材', children: mediaManagementTab },
          { key: 'recall', label: '召回测试', children: recallTestTab },
        ]}
      />
      {mediaAssetModals}
    </Space>
  );
};
