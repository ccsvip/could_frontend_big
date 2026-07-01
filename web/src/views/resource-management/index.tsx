import {
  IconTrash,
  IconEdit,
  IconEye,
  IconPhoto,
  IconPlus,
  IconReload,
  IconUpload,
} from '@tabler/icons-react';
import {
  Button,
  Card,
  Empty,
  Form,
  Image,
  Input,
  message,
  Modal,
  Pagination,
  Popconfirm,
  Progress,
  Select,
  Segmented,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  batchCreateImageResources,
  createImageResource,
  createVideoResource,
  deleteImageResource,
  deleteVideoResource,
  fetchImageResources,
  fetchResourceUploadConfig,
  fetchVideoResources,
  presignResourceUpload,
  uploadFileToPresignedUrl,
  updateImageResource,
  updateVideoResource,
  type ResourceCategory,
  type ResourceListQuery,
  type ResourceRecord,
  type ResourceType,
  type VideoUploadConfig,
} from '../../api/modules/resources';
import { useAuthStore } from '../../store/auth';

const categoryOptions = [
  { label: '全部分类', value: 'all' },
  { label: '横屏', value: 'horizontal' },
  { label: '竖屏', value: 'vertical' },
  { label: '未分类', value: 'uncategorized' },
] as const;

type ResourceManagementPageProps = {
  resourceType: ResourceType;
};

type ResourceFormValues = {
  name: string;
  category: ResourceCategory;
  description?: string;
  cloudUrl?: string;
  storageBackend?: string;
  file?: UploadFile[];
  clearFile?: boolean;
  isDigitalHumanBackground?: boolean;
};

type BatchUploadFormValues = {
  category: ResourceCategory;
  description?: string;
  files?: UploadFile[];
  isDigitalHumanBackground?: boolean;
};

const resourceConfig = {
  image: {
    title: '图片管理',
    description: '集中维护图片资源，支持分类、分页、空态提示与大图预览。',
    viewPermission: 'resources.images.view',
    createPermission: 'resources.images.create',
    updatePermission: 'resources.images.update',
    deletePermission: 'resources.images.delete',
    fetcher: fetchImageResources,
    creator: createImageResource,
    updater: updateImageResource,
    remover: deleteImageResource,
    accept: 'image/*',
  },
  video: {
    title: '视频管理',
    description: '集中维护视频资源，支持分类、分页、在线播放与权限控制。',
    viewPermission: 'resources.videos.view',
    createPermission: 'resources.videos.create',
    updatePermission: 'resources.videos.update',
    deletePermission: 'resources.videos.delete',
    fetcher: fetchVideoResources,
    creator: createVideoResource,
    updater: updateVideoResource,
    remover: deleteVideoResource,
    accept: 'video/*',
  },
} as const;

const videoThumbnailCache = new Map<string, string | null>();
const videoThumbnailRequests = new Map<string, Promise<string | null>>();
const videoThumbnailQueue: Array<() => void> = [];
let activeVideoThumbnailTasks = 0;

const VIDEO_THUMBNAIL_CONCURRENCY = 2;
const VIDEO_THUMBNAIL_CAPTURE_TIME = 0.8;
const VIDEO_THUMBNAIL_TIMEOUT_MS = 10000;
const resourceGridClassName = 'grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4';
const imageUsageOptions = [
  { label: '数字人背景图', value: 'background' },
  { label: '图片素材', value: 'material' },
] as const;
type ImageUsage = typeof imageUsageOptions[number]['value'];

const formatFileMB = (bytes: number | null | undefined) => {
  if (bytes == null) {
    return '不限制';
  }
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
};
const previewModalWidth = {
  imageHorizontal: 960,
  imageVertical: 560,
  video: 'min(92vw, 1180px)',
} as const;

type VideoResourceCardCoverProps = {
  item: ResourceRecord;
  sourceUrl: string;
};

const getResourceSourceUrl = (item: ResourceRecord) => item.fileUrl || item.cloudUrl || '';
const hasResourceSource = (item: ResourceRecord) => Boolean(getResourceSourceUrl(item));

const getVideoPreviewTime = (duration: number) => {
  if (!Number.isFinite(duration) || duration <= 0.2) {
    return 0;
  }

  return Math.min(VIDEO_THUMBNAIL_CAPTURE_TIME, Math.max(0, duration / 2));
};

const runNextVideoThumbnailTask = () => {
  while (activeVideoThumbnailTasks < VIDEO_THUMBNAIL_CONCURRENCY && videoThumbnailQueue.length > 0) {
    const task = videoThumbnailQueue.shift();
    if (task) task();
  }
};

const captureVideoThumbnail = (sourceUrl: string) => new Promise<string | null>((resolve) => {
  const videoElement = document.createElement('video');
  let settled = false;
  let waitingForSeek = false;
  let frameCaptureScheduled = false;
  const timeoutId = window.setTimeout(() => finish(null), VIDEO_THUMBNAIL_TIMEOUT_MS);

  const cleanup = () => {
    window.clearTimeout(timeoutId);
    videoElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
    videoElement.removeEventListener('loadeddata', handleFrameReady);
    videoElement.removeEventListener('seeked', handleFrameReady);
    videoElement.removeEventListener('error', handleError);
    videoElement.pause();
    videoElement.removeAttribute('src');
    videoElement.load();
  };

  const finish = (thumbnail: string | null) => {
    if (settled) return;
    settled = true;
    cleanup();
    resolve(thumbnail);
  };

  const scheduleFrameCapture = () => {
    if (settled || waitingForSeek || frameCaptureScheduled || videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return;
    }

    frameCaptureScheduled = true;
    const runCapture = () => {
      frameCaptureScheduled = false;
      handleFrameReady();
    };
    const requestVideoFrameCallback = (
      videoElement as HTMLVideoElement & {
        requestVideoFrameCallback?: (callback: () => void) => number;
      }
    ).requestVideoFrameCallback;

    if (requestVideoFrameCallback) {
      requestVideoFrameCallback.call(videoElement, runCapture);
      return;
    }

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(runCapture);
    });
  };

  const handleFrameReady = () => {
    if (waitingForSeek) {
      return;
    }

    if (!videoElement.videoWidth || !videoElement.videoHeight) {
      finish(null);
      return;
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = videoElement.videoWidth;
      canvas.height = videoElement.videoHeight;
      const context = canvas.getContext('2d');

      if (!context) {
        finish(null);
        return;
      }

      context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
      finish(canvas.toDataURL('image/jpeg'));
    } catch {
      finish(null);
    }
  };

  const handleLoadedMetadata = () => {
    const targetTime = getVideoPreviewTime(videoElement.duration);

    if (targetTime > 0) {
      waitingForSeek = true;
      try {
        videoElement.currentTime = targetTime;
      } catch {
        waitingForSeek = false;
        scheduleFrameCapture();
      }
      return;
    }

    scheduleFrameCapture();
  };

  const handleSeeked = () => {
    waitingForSeek = false;
    scheduleFrameCapture();
  };

  const handleError = () => finish(null);

  videoElement.preload = 'auto';
  videoElement.muted = true;
  videoElement.playsInline = true;
  videoElement.crossOrigin = 'anonymous';
  videoElement.addEventListener('loadedmetadata', handleLoadedMetadata);
  videoElement.addEventListener('loadeddata', handleFrameReady);
  videoElement.addEventListener('seeked', handleSeeked);
  videoElement.addEventListener('error', handleError);
  videoElement.src = sourceUrl;
  videoElement.load();
});

const loadVideoThumbnail = (sourceUrl: string) => {
  const cached = videoThumbnailCache.get(sourceUrl);
  if (cached !== undefined) {
    return Promise.resolve(cached);
  }

  const pending = videoThumbnailRequests.get(sourceUrl);
  if (pending) {
    return pending;
  }

  const request = new Promise<string | null>((resolve) => {
    const runTask = () => {
      activeVideoThumbnailTasks += 1;
      captureVideoThumbnail(sourceUrl)
        .then((thumbnail) => {
          videoThumbnailCache.set(sourceUrl, thumbnail);
          resolve(thumbnail);
        })
        .catch(() => {
          videoThumbnailCache.set(sourceUrl, null);
          resolve(null);
        })
        .finally(() => {
          activeVideoThumbnailTasks -= 1;
          videoThumbnailRequests.delete(sourceUrl);
          runNextVideoThumbnailTask();
        });
    };

    videoThumbnailQueue.push(runTask);
    runNextVideoThumbnailTask();
  });

  videoThumbnailRequests.set(sourceUrl, request);
  return request;
};

type VideoFramePreviewProps = {
  sourceUrl: string;
  itemName: string;
  onReady: () => void;
};

const VideoFramePreview = ({ sourceUrl, itemName, onReady }: VideoFramePreviewProps) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const waitingForSeekRef = useRef(false);
  const readyScheduledRef = useRef(false);

  useEffect(() => {
    waitingForSeekRef.current = false;
    readyScheduledRef.current = false;
  }, [sourceUrl]);

  const markReady = () => {
    const videoElement = videoRef.current;
    if (!videoElement || readyScheduledRef.current) {
      return;
    }

    readyScheduledRef.current = true;
    const finish = () => {
      waitingForSeekRef.current = false;
      readyScheduledRef.current = false;
      onReady();
    };
    const requestVideoFrameCallback = (
      videoElement as HTMLVideoElement & {
        requestVideoFrameCallback?: (callback: () => void) => number;
      }
    ).requestVideoFrameCallback;

    if (requestVideoFrameCallback) {
      requestVideoFrameCallback.call(videoElement, finish);
      return;
    }

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(finish);
    });
  };

  const handleLoadedMetadata = () => {
    const videoElement = videoRef.current;
    if (!videoElement) {
      return;
    }

    const targetTime = getVideoPreviewTime(videoElement.duration);
    if (targetTime <= 0) {
      markReady();
      return;
    }

    waitingForSeekRef.current = true;
    try {
      videoElement.currentTime = targetTime;
    } catch {
      markReady();
    }
  };

  const handleLoadedData = () => {
    if (!waitingForSeekRef.current) {
      markReady();
    }
  };

  return (
    <video
      ref={videoRef}
      src={sourceUrl}
      muted
      playsInline
      preload="auto"
      aria-label={`${itemName} 视频封面预览`}
      onLoadedMetadata={handleLoadedMetadata}
      onLoadedData={handleLoadedData}
      onSeeked={markReady}
      onCanPlay={handleLoadedData}
      className="absolute inset-0 h-full w-full object-cover"
    />
  );
};

type VideoThumbnailPlaceholderProps = {
  status: 'idle' | 'loading' | 'ready' | 'fallback';
};

const VideoThumbnailPlaceholder = ({ status }: VideoThumbnailPlaceholderProps) => (
  <div className="absolute inset-0 flex items-center justify-center bg-slate-900 text-slate-200">
    <Space direction="vertical" align="center" size={8}>
      <IconPhoto className="text-4xl text-slate-300/80" />
      <span className="text-sm">{status === 'loading' ? '正在加载视频缩略图' : '暂无视频缩略图'}</span>
    </Space>
  </div>
);

const VideoResourceCardCover = ({ item, sourceUrl }: VideoResourceCardCoverProps) => {
  const coverRef = useRef<HTMLDivElement | null>(null);
  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(() => item.thumbnailUrl || videoThumbnailCache.get(sourceUrl) || null);
  const [fallbackPreviewReady, setFallbackPreviewReady] = useState(false);
  const [thumbnailStatus, setThumbnailStatus] = useState<'idle' | 'loading' | 'ready' | 'fallback'>(() => {
    if (item.thumbnailUrl) return 'ready';
    const cached = videoThumbnailCache.get(sourceUrl);
    if (cached === undefined) return sourceUrl ? 'idle' : 'fallback';
    return cached ? 'ready' : 'fallback';
  });

  useEffect(() => {
    setFallbackPreviewReady(false);

    if (item.thumbnailUrl) {
      setThumbnailSrc(item.thumbnailUrl);
      setThumbnailStatus('ready');
      return;
    }

    if (!sourceUrl) {
      setThumbnailSrc(null);
      setThumbnailStatus('fallback');
      return;
    }

    const cached = videoThumbnailCache.get(sourceUrl);
    if (cached !== undefined) {
      setThumbnailSrc(cached);
      setThumbnailStatus(cached ? 'ready' : 'fallback');
      return;
    }

    let cancelled = false;
    const startLoading = () => {
      setThumbnailStatus('loading');
      void loadVideoThumbnail(sourceUrl).then((thumbnail) => {
        if (cancelled) return;
        setThumbnailSrc(thumbnail);
        setThumbnailStatus(thumbnail ? 'ready' : 'fallback');
      });
    };

    const node = coverRef.current;
    if (node && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          observer.disconnect();
          startLoading();
        }
      }, { rootMargin: '120px' });

      observer.observe(node);
      return () => {
        cancelled = true;
        observer.disconnect();
      };
    }

    startLoading();
    return () => {
      cancelled = true;
    };
  }, [item.thumbnailUrl, sourceUrl]);

  return (
    <div ref={coverRef} className={`relative block w-full overflow-hidden bg-slate-950 ${item.category === 'vertical' ? 'aspect-[9/16]' : 'aspect-video'}`}>
      {thumbnailSrc ? (
        <img
          src={thumbnailSrc}
          alt={`${item.name} 缩略图`}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : sourceUrl ? (
        <>
          <VideoFramePreview
            sourceUrl={sourceUrl}
            itemName={item.name}
            onReady={() => setFallbackPreviewReady(true)}
          />
          {!fallbackPreviewReady ? <VideoThumbnailPlaceholder status={thumbnailStatus} /> : null}
        </>
      ) : (
        <VideoThumbnailPlaceholder status={thumbnailStatus} />
      )}

      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/60 via-slate-950/10 to-transparent" />
    </div>
  );
};

export const ResourceManagementPage = ({ resourceType }: ResourceManagementPageProps) => {
  const config = resourceConfig[resourceType];
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission(config.createPermission);
  const canUpdate = hasPermission(config.updatePermission);
  const canDelete = hasPermission(config.deletePermission);

  const [items, setItems] = useState<ResourceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState<ResourceCategory | 'all'>('all');
  const [keyword, setKeyword] = useState('');
  const [previewItem, setPreviewItem] = useState<ResourceRecord | null>(null);
  const [editingItem, setEditingItem] = useState<ResourceRecord | null>(null);
  const [formVisible, setFormVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [imageUsage, setImageUsage] = useState<ImageUsage>('material');
  const [batchModalVisible, setBatchModalVisible] = useState(false);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [resourceUploadConfig, setResourceUploadConfig] = useState<(VideoUploadConfig & { imageDirectUploadEnabled?: boolean }) | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{
    visible: boolean;
    percent: number;
    loaded: number;
    total: number;
    status: 'active' | 'success' | 'exception';
    message: string;
  }>({ visible: false, percent: 0, loaded: 0, total: 0, status: 'active', message: '' });
  const uploadAbortRef = useRef<AbortController | null>(null);
  const [form] = Form.useForm<ResourceFormValues>();
  const [batchForm] = Form.useForm<BatchUploadFormValues>();
  const batchFiles = Form.useWatch('files', batchForm) || [];

  const query = useMemo<ResourceListQuery>(() => ({
    page,
    category,
    keyword,
    isDigitalHumanBackground: resourceType === 'image' ? imageUsage === 'background' : undefined,
  }), [page, category, keyword, resourceType, imageUsage]);

  const loadData = useCallback(async (nextQuery: ResourceListQuery = query) => {
    setLoading(true);
    try {
      const response = await config.fetcher(nextQuery);
      setItems(response.results);
      setTotal(response.count);
    } catch {
      // 错误由拦截器处理
    } finally {
      setLoading(false);
    }
  }, [config, query]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    fetchResourceUploadConfig()
      .then(setResourceUploadConfig)
      .catch(() => {
        setResourceUploadConfig(null);
      });
  }, []);

  const openCreateModal = () => {
    setEditingItem(null);
    setUploadProgress({ visible: false, percent: 0, loaded: 0, total: 0, status: 'active', message: '' });
    form.resetFields();
    form.setFieldsValue({
      category: 'uncategorized',
      clearFile: false,
      cloudUrl: '',
      file: [],
      isDigitalHumanBackground: resourceType === 'image' && imageUsage === 'background',
    });
    setFormVisible(true);
  };

  const openEditModal = (item: ResourceRecord) => {
    setEditingItem(item);
    setUploadProgress({ visible: false, percent: 0, loaded: 0, total: 0, status: 'active', message: '' });
    form.setFieldsValue({
      name: item.name,
      category: item.category,
      description: item.description,
      cloudUrl: item.cloudUrl || '',
      clearFile: false,
      file: [],
      isDigitalHumanBackground: item.isDigitalHumanBackground,
    });
    setFormVisible(true);
  };

  const openBatchModal = () => {
    batchForm.resetFields();
    batchForm.setFieldsValue({
      category: 'uncategorized',
      files: [],
      isDigitalHumanBackground: imageUsage === 'background',
    });
    setBatchModalVisible(true);
  };

  const closeBatchModal = () => {
    setBatchModalVisible(false);
    batchForm.resetFields();
  };

  const closeFormModal = () => {
    uploadAbortRef.current?.abort();
    uploadAbortRef.current = null;
    setFormVisible(false);
    setEditingItem(null);
    setUploadProgress({ visible: false, percent: 0, loaded: 0, total: 0, status: 'active', message: '' });
    form.resetFields();
  };

  const handleDelete = async (item: ResourceRecord) => {
    try {
      await config.remover(item.id);
      if (items.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        void loadData();
      }
    } catch {
      // 错误由拦截器处理
    }
  };

  const uploadResourceToObjectStorage = async (file: File): Promise<{ objectKey: string; objectSize: number; storageBackend?: string } | null> => {
    if (resourceUploadConfig && !resourceUploadConfig.enabled) {
      message.error(resourceUploadConfig.storageBackend === 'r2' ? 'R2 存储桶未配置完整，请联系超级管理员' : '视频直传未启用，请填写云端 URL 或联系超级管理员');
      return null;
    }
    const maxSizeBytes = resourceType === 'video' ? resourceUploadConfig?.maxSizeBytes : undefined;
    if (maxSizeBytes && file.size > maxSizeBytes) {
      message.error(`视频大小超出限制，最多 ${resourceUploadConfig?.maxSizeMB ?? Math.floor(maxSizeBytes / 1024 / 1024)}MB`);
      return null;
    }

    if (resourceType === 'video' && resourceUploadConfig?.quotaLimited && resourceUploadConfig.remainingBytes != null && file.size > resourceUploadConfig.remainingBytes) {
      message.error('公司视频剩余额度不足，请联系超级管理员调整额度');
      return null;
    }

    const controller = new AbortController();
    uploadAbortRef.current = controller;
    setUploadProgress({
      visible: true,
      percent: 0,
      loaded: 0,
      total: file.size,
      status: 'active',
      message: '正在申请上传地址...',
    });

    try {
      const presigned = await presignResourceUpload({
        resourceType,
        filename: file.name,
        contentType: file.type || 'application/octet-stream',
        fileSize: file.size,
      });
      setUploadProgress((prev) => ({ ...prev, message: '正在上传...' }));
      await uploadFileToPresignedUrl(presigned.uploadUrl, file, {
        headers: presigned.headers,
        signal: controller.signal,
        onProgress: (percent, loaded, total) => {
          setUploadProgress({
            visible: true,
            percent,
            loaded,
            total,
            status: 'active',
            message: percent >= 100 ? '上传完成，正在保存...' : `已上传 ${percent}%`,
          });
        },
      });
      setUploadProgress((prev) => ({ ...prev, percent: 100, status: 'success', message: '上传完成' }));
      return { objectKey: presigned.objectKey, objectSize: presigned.objectSize ?? file.size, storageBackend: presigned.storageBackend };
    } catch (error) {
      const aborted = controller.signal.aborted || (error as Error)?.name === 'CanceledError';
      setUploadProgress((prev) => ({
        ...prev,
        status: 'exception',
        message: aborted ? '上传已取消' : '上传失败',
      }));
      if (!aborted) {
        message.error(resourceUploadConfig?.storageBackend === 'r2' ? '上传到 R2 失败，请重试' : '上传到对象存储失败，请重试');
      }
      return null;
    } finally {
      uploadAbortRef.current = null;
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const selectedFile = values.file?.[0]?.originFileObj;
      const cloudUrl = showCloudUrlField ? values.cloudUrl?.trim() || '' : '';
      let objectKey = '';
      let objectSize: number | null = null;
      let file = selectedFile;

      if (resourceType === 'video' && selectedFile && cloudUrl) {
        message.error('上传视频和云端 URL 只能二选一');
        return;
      }
      if (resourceType === 'video' && !selectedFile && !cloudUrl && !editingItem?.hasFile) {
        message.error(showCloudUrlField ? '请上传视频或填写云端 URL' : '请上传视频');
        return;
      }

      if (((resourceType === 'video') || (resourceType === 'image' && resourceUploadConfig?.storageBackend === 'r2')) && selectedFile) {
        const uploaded = await uploadResourceToObjectStorage(selectedFile);
        if (!uploaded) {
          return;
        }
        objectKey = uploaded.objectKey;
        objectSize = uploaded.objectSize;
        const storageBackend = uploaded.storageBackend;
        file = undefined;
        form.setFieldValue('storageBackend', storageBackend);
      }

      const payload = {
        name: values.name,
        category: values.category,
        description: values.description,
        cloudUrl,
        objectKey: objectKey || undefined,
        objectSize,
        storageBackend: form.getFieldValue('storageBackend') || undefined,
        file,
        isDigitalHumanBackground: resourceType === 'image' ? Boolean(values.isDigitalHumanBackground) : false,
        clearFile: resourceType === 'image' ? Boolean(values.clearFile) : false,
      };

      if (editingItem) {
        await config.updater(editingItem.id, payload);
      } else {
        await config.creator(payload);
      }

      if (resourceType === 'video' && objectSize != null) {
        setResourceUploadConfig((current) => current
          ? {
              ...current,
              usedBytes: current.usedBytes + objectSize,
              remainingBytes: current.remainingBytes == null ? null : Math.max(0, current.remainingBytes - objectSize),
              usedMB: Math.round(((current.usedBytes + objectSize) / 1024 / 1024) * 100) / 100,
              remainingMB: current.remainingBytes == null
                ? null
                : Math.round((Math.max(0, current.remainingBytes - objectSize) / 1024 / 1024) * 100) / 100,
            }
          : current);
      }

      closeFormModal();
      if (!editingItem) {
        setPage(1);
      }
      if (!editingItem && resourceType === 'image') {
        const nextImageUsage: ImageUsage = values.isDigitalHumanBackground ? 'background' : 'material';
        setImageUsage(nextImageUsage);
        setCategory(values.category);
        void loadData({
          page: 1,
          category: values.category,
          keyword,
          isDigitalHumanBackground: nextImageUsage === 'background',
        });
      } else {
        void loadData(editingItem ? query : { ...query, page: 1 });
      }
    } catch {
      // 错误由拦截器处理
    } finally {
      setSubmitting(false);
    }
  };

  const handleBatchSubmit = async () => {
    try {
      const values = await batchForm.validateFields();
      const files = values.files?.map((file) => file.originFileObj).filter(Boolean) as File[];
      if (!files.length) {
        message.error('请至少选择一个图片文件');
        return;
      }
      setBatchSubmitting(true);
      if (resourceUploadConfig?.storageBackend === 'r2') {
        for (const file of files) {
          const uploaded = await uploadResourceToObjectStorage(file);
          if (!uploaded) {
            return;
          }
          await createImageResource({
            name: file.name.replace(/\.[^.]+$/, '') || file.name,
            category: values.category,
            description: values.description,
            objectKey: uploaded.objectKey,
            objectSize: uploaded.objectSize,
            storageBackend: uploaded.storageBackend,
            isDigitalHumanBackground: Boolean(values.isDigitalHumanBackground),
          });
        }
      } else {
        await batchCreateImageResources({
          files,
          category: values.category,
          description: values.description,
          isDigitalHumanBackground: Boolean(values.isDigitalHumanBackground),
        });
      }
      const nextImageUsage: ImageUsage = values.isDigitalHumanBackground ? 'background' : 'material';
      message.success(`已上传 ${files.length} 个图片资源`);
      closeBatchModal();
      setPage(1);
      setImageUsage(nextImageUsage);
      setCategory(values.category);
      void loadData({
        page: 1,
        category: values.category,
        keyword,
        isDigitalHumanBackground: nextImageUsage === 'background',
      });
    } catch {
      // 错误由拦截器处理
    } finally {
      setBatchSubmitting(false);
    }
  };

  const emptyDescription = resourceType === 'image' ? '暂无图片资源，请先上传图片。' : '暂无视频资源，请先上传视频。';
  const showCloudUrlField = resourceType === 'image' || resourceUploadConfig?.allowCloudUrl !== false;

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Typography.Title level={3} className="!mb-1 !text-slate-900">
              {config.title}
            </Typography.Title>
            <Typography.Text className="!text-slate-500">{config.description}</Typography.Text>
          </div>
          <Space wrap>
            {resourceType === 'image' ? (
              <Segmented
                value={imageUsage}
                options={imageUsageOptions as unknown as { label: string; value: string }[]}
                onChange={(value) => {
                  setImageUsage(value as ImageUsage);
                  setPage(1);
                }}
              />
            ) : null}
            <Input.Search
              allowClear
              placeholder="搜索资源名称"
              onSearch={(value) => {
                setKeyword(value.trim());
                setPage(1);
              }}
              className="!w-60"
            />
            <Select
              value={category}
              options={categoryOptions as unknown as { label: string; value: string }[]}
              onChange={(value) => {
                setCategory(value as ResourceCategory | 'all');
                setPage(1);
              }}
              className="!w-36"
            />
            <Button icon={<IconReload />} onClick={() => void loadData()}>
              刷新
            </Button>
            {canCreate ? (
              <>
                {resourceType === 'image' ? (
                  <Button icon={<IconUpload />} onClick={openBatchModal}>
                    批量上传
                  </Button>
                ) : null}
                <Button type="primary" icon={<IconPlus />} onClick={openCreateModal}>
                  新建资源
                </Button>
              </>
            ) : null}
          </Space>
        </div>
      </Card>

      <div className={resourceGridClassName}>
        {items.map((item) => {
          const sourceUrl = getResourceSourceUrl(item);
          const hasSource = hasResourceSource(item);

          return (
            <Card
              key={item.id}
              variant="borderless"
              loading={loading}
              className="!rounded-xl !border !border-slate-200/70 !shadow-card overflow-hidden"
              cover={
                hasSource ? (
                  resourceType === 'image' ? (
                    <div className={`relative block w-full overflow-hidden bg-slate-100 flex items-center justify-center ${item.category === 'vertical' ? 'aspect-[9/16]' : 'aspect-video'}`}>
                      <img src={sourceUrl} alt={item.name} className="absolute inset-0 h-full w-full object-cover" />
                    </div>
                  ) : (
                    <VideoResourceCardCover item={item} sourceUrl={sourceUrl} />
                  )
                ) : (
                  <div className={`flex items-center justify-center bg-slate-100 text-slate-400 ${item.category === 'vertical' ? 'aspect-[9/16]' : 'aspect-video'}`}>
                    <Space direction="vertical" align="center">
                      <IconPhoto className="text-4xl" />
                      <span>{resourceType === 'image' ? '未上传图片' : '未配置视频地址'}</span>
                    </Space>
                  </div>
                )
              }
              actions={[
                <Button key="preview" type="text" icon={<IconEye />} onClick={() => setPreviewItem(item)} disabled={!hasSource}>
                  预览
                </Button>,
                canUpdate ? (
                  <Button key="edit" type="text" icon={<IconEdit />} onClick={() => openEditModal(item)}>
                    编辑
                  </Button>
                ) : (
                  <span key="edit-placeholder" />
                ),
                canDelete ? (
                  <Popconfirm key="delete" title="确认删除该资源吗？" onConfirm={() => void handleDelete(item)}>
                    <Button type="text" danger icon={<IconTrash />}>
                      删除
                    </Button>
                  </Popconfirm>
                ) : (
                  <span key="delete-placeholder" />
                ),
              ]}
            >
              <Space direction="vertical" size={10} className="w-full">
                <div className="flex items-start justify-between gap-3">
                  <Typography.Title level={5} className="!mb-0 !text-slate-900">
                    {item.name}
                  </Typography.Title>
                  <Tag color={hasSource ? 'processing' : 'default'}>{hasSource ? (item.hasFile ? '已上传' : '云端') : '空资源'}</Tag>
                </div>
                <Space wrap>
                  <Tag color="blue">{item.categoryLabel}</Tag>
                  <Tag>{item.resourceTypeLabel}</Tag>
                  {resourceType === 'image' && item.isDigitalHumanBackground ? <Tag color="purple">数字人背景图</Tag> : null}
                </Space>
                <Typography.Paragraph className="!mb-0 !text-slate-500" ellipsis={{ rows: 2 }}>
                  {item.description || '暂无资源说明'}
                </Typography.Paragraph>
                <Typography.Text className="!text-slate-400 text-xs">更新时间：{item.updated_at}</Typography.Text>
              </Space>
            </Card>
          );
        })}
      </div>

      {!loading && items.length === 0 ? (
        <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
          <Empty description={emptyDescription} />
        </Card>
      ) : null}

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex justify-end">
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger={false}
            onChange={(nextPage) => setPage(nextPage)}
          />
        </div>
      </Card>

      <Modal
        title={editingItem ? `编辑${config.title}` : `新建${config.title}`}
        open={formVisible}
        onCancel={closeFormModal}
        onOk={() => void handleSubmit()}
        confirmLoading={submitting}
        destroyOnHidden
        forceRender
        okText={editingItem ? '保存' : '创建'}
        cancelText="取消"
      >
        <Form<ResourceFormValues> form={form} layout="vertical">
          <Form.Item label="资源名称" name="name" rules={[{ required: true, message: '请输入资源名称' }]}>
            <Input placeholder="请输入资源名称" />
          </Form.Item>
          <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions.slice(1) as unknown as { label: string; value: string }[]} />
          </Form.Item>
          <Form.Item label="资源说明" name="description">
            <Input.TextArea rows={3} placeholder="请输入资源说明" />
          </Form.Item>
          {resourceType === 'image' ? (
            <Form.Item label="作为数字人背景图" name="isDigitalHumanBackground" valuePropName="checked">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          ) : null}
          {showCloudUrlField ? (
            <Form.Item label="云端URL地址（选填）" name="cloudUrl">
              <Input placeholder="请输入云端 URL（选填）" />
            </Form.Item>
          ) : null}
          <Form.Item
            label={resourceType === 'image' ? '上传图片（选填）' : '上传视频（选填）'}
            name="file"
            valuePropName="fileList"
            getValueFromEvent={(event) => event?.fileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept={config.accept}>
              <Button icon={<IconUpload />}>选择文件</Button>
            </Upload>
          </Form.Item>
          {resourceType === 'video' ? (
            <Space direction="vertical" size={8} className="mb-3 w-full">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                <Space wrap size={12}>
                  <span>单文件最大：{resourceUploadConfig ? formatFileMB(resourceUploadConfig.maxSizeBytes) : '加载中'}</span>
                  <span>已用：{formatFileMB(resourceUploadConfig?.usedBytes)}</span>
                  <span>剩余：{resourceUploadConfig?.quotaLimited ? formatFileMB(resourceUploadConfig.remainingBytes) : '不限制'}</span>
                </Space>
              </div>
              {uploadProgress.visible ? (
                <div className="rounded-lg border border-slate-200 px-3 py-2">
                  <div className="mb-2 flex items-center justify-between gap-3 text-sm text-slate-600">
                    <span>{uploadProgress.message}</span>
                    <span>
                      {formatFileMB(uploadProgress.loaded)} / {formatFileMB(uploadProgress.total)}
                    </span>
                  </div>
                  <Progress percent={uploadProgress.percent} status={uploadProgress.status} size="small" />
                  {uploadProgress.status === 'active' ? (
                    <Button size="small" className="mt-2" onClick={() => uploadAbortRef.current?.abort()}>
                      取消上传
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </Space>
          ) : null}
          {resourceType === 'image' && editingItem ? (
            <Form.Item label="图片清空" name="clearFile">
              <Select
                options={[
                  { value: false, label: '保留现有图片' },
                  { value: true, label: '清空当前图片' },
                ]}
              />
            </Form.Item>
          ) : null}
          {resourceType === 'image' && editingItem && !editingItem.hasFile ? (
            <Typography.Text className="!text-slate-500">当前资源没有上传图片，保存时可继续保持空态。</Typography.Text>
          ) : null}
        </Form>
      </Modal>

      <Modal
        title={previewItem?.name || '资源预览'}
        open={!!previewItem}
        footer={null}
        onCancel={() => setPreviewItem(null)}
        width={
          resourceType === 'video'
            ? previewModalWidth.video
            : previewItem?.category === 'vertical'
              ? previewModalWidth.imageVertical
              : previewModalWidth.imageHorizontal
        }
        destroyOnHidden
      >
        {previewItem ? (
          hasResourceSource(previewItem) ? (
            resourceType === 'image' ? (
              <Image src={getResourceSourceUrl(previewItem)} alt={previewItem.name} className="w-full max-h-[75vh] object-contain bg-slate-100 rounded-lg" />
            ) : (
              <div className="flex h-[78vh] max-h-[820px] min-h-[360px] w-full items-center justify-center overflow-hidden rounded-xl bg-black">
                <video src={getResourceSourceUrl(previewItem)} controls className="h-full w-full object-contain" />
              </div>
            )
          ) : (
            <Empty description={resourceType === 'image' ? '该图片资源当前为空' : '该视频资源当前未配置视频地址'} />
          )
        ) : null}
      </Modal>

      <Modal
        title="批量上传图片"
        open={batchModalVisible}
        onCancel={closeBatchModal}
        onOk={() => void handleBatchSubmit()}
        confirmLoading={batchSubmitting}
        destroyOnHidden
        forceRender
        okText="上传"
        cancelText="取消"
      >
        <Form<BatchUploadFormValues> form={batchForm} layout="vertical">
          <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions.slice(1) as unknown as { label: string; value: string }[]} />
          </Form.Item>
          <Form.Item label="作为数字人背景图" name="isDigitalHumanBackground" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
          <Form.Item label="资源说明" name="description">
            <Input.TextArea rows={3} placeholder="请输入资源说明" />
          </Form.Item>
          <Form.Item
            label="图片文件"
            name="files"
            valuePropName="fileList"
            getValueFromEvent={(event) => event?.fileList}
            rules={[{ required: true, message: '请选择图片文件' }]}
          >
            <Upload
              beforeUpload={() => false}
              multiple
              accept="image/*"
              listType="text"
              showUploadList={{ showPreviewIcon: false }}
              className="[&_.ant-upload-list]:max-h-56 [&_.ant-upload-list]:overflow-y-auto [&_.ant-upload-list]:rounded-lg [&_.ant-upload-list]:border [&_.ant-upload-list]:border-slate-100 [&_.ant-upload-list]:bg-slate-50/60 [&_.ant-upload-list]:px-2"
            >
              <Button icon={<IconUpload />}>选择多个图片</Button>
            </Upload>
          </Form.Item>
          {batchFiles.length > 0 ? (
            <Typography.Text className="!text-slate-500">已选择 {batchFiles.length} 个图片文件</Typography.Text>
          ) : null}
        </Form>
      </Modal>
    </Space>
  );
};
