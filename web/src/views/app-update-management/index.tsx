import {
  IconApps,
  IconCircleCheck,
  IconFileText,
  IconRefresh,
  IconUpload,
} from '@tabler/icons-react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import axios from 'axios';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createAppRelease,
  fetchAppReleases,
  fetchForceUpgradeThreshold,
  updateAppReleaseActive,
  updateForceUpgradeThreshold,
  type AppReleaseRecord,
  type CreateAppReleasePayload,
} from '../../api/modules/app-updates';

type ReleaseFormValues = Omit<CreateAppReleasePayload, 'apkFile'>;

type UploadErrorResponse = {
  details?: Partial<Record<keyof ReleaseFormValues | 'apkFile', string | string[]>>;
};

const formatFileSize = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const formatDateTime = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false });

export const AppUpdateManagementPage = () => {
  const [form] = Form.useForm<ReleaseFormValues>();
  const [releases, setReleases] = useState<AppReleaseRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [changingReleaseId, setChangingReleaseId] = useState<string | null>(null);

  const [threshold, setThreshold] = useState(0);
  const [thresholdUpdating, setThresholdUpdating] = useState(false);
  const [thresholdDraft, setThresholdDraft] = useState(0);
  const [latestVersionCode, setLatestVersionCode] = useState<number | null>(null);

  const loadReleases = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAppReleases();
      setReleases(data.results);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadThreshold = useCallback(async () => {
    try {
      const data = await fetchForceUpgradeThreshold();
      setThreshold(data.forceUpgradeVersionCode);
      setThresholdDraft(data.forceUpgradeVersionCode);
      setLatestVersionCode(data.latestVersionCode);
    } catch {
      // 没有发布记录时使用默认值 0
      setLatestVersionCode(null);
    }
  }, []);

  useEffect(() => {
    void loadReleases();
    void loadThreshold();
  }, [loadReleases, loadThreshold]);

  const activeRelease = useMemo(() => releases.find((release) => release.isActive) ?? null, [releases]);

  const openUpload = () => {
    form.resetFields();
    form.setFieldsValue({ releaseNotes: '', isActive: true });
    setSelectedFile(null);
    setUploadProgress(0);
    setUploadOpen(true);
  };

  const handleUpload = async () => {
    const values = await form.validateFields();
    if (!selectedFile) {
      message.error('请选择 APK 文件');
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      await createAppRelease({ ...values, apkFile: selectedFile }, setUploadProgress);
      message.success('新版本上传成功');
      setUploadOpen(false);
      await Promise.all([loadReleases(), loadThreshold()]);
    } catch (error) {
      if (axios.isAxiosError<UploadErrorResponse>(error) && error.response?.data.details) {
        const { apkFile, ...fieldErrors } = error.response.data.details;
        form.setFields(Object.entries(fieldErrors).map(([name, errors]) => ({
          name: name as keyof ReleaseFormValues,
          errors: Array.isArray(errors) ? errors : [errors],
        })));
        if (apkFile) {
          message.error(Array.isArray(apkFile) ? apkFile[0] : apkFile);
        }
      }
    } finally {
      setUploading(false);
    }
  };

  const handleActiveChange = async (release: AppReleaseRecord, checked: boolean) => {
    setChangingReleaseId(release.releaseId);
    try {
      await updateAppReleaseActive(release.releaseId, checked);
      message.success(checked ? '发布版本已启用' : '发布版本已停用');
      await loadReleases();
    } finally {
      setChangingReleaseId(null);
    }
  };

  const handleThresholdConfirm = async () => {
    if (thresholdDraft === threshold) return;
    if (latestVersionCode == null) {
      message.error('没有发布记录，请先上传 APK');
      return;
    }
    if (thresholdDraft > latestVersionCode) {
      message.error(`强制升级阈值不得高于最新上传版本号 ${latestVersionCode}`);
      return;
    }
    setThresholdUpdating(true);
    try {
      const data = await updateForceUpgradeThreshold(thresholdDraft);
      message.success('强制升级阈值已更新，已向设备发送通知');
      setThreshold(data.forceUpgradeVersionCode);
      setThresholdDraft(data.forceUpgradeVersionCode);
      setLatestVersionCode(data.latestVersionCode);
      await loadReleases();
    } catch (error) {
      if (axios.isAxiosError<{ message: string }>(error) && error.response?.data?.message) {
        message.error(error.response.data.message);
      } else {
        message.error('更新失败');
      }
    } finally {
      setThresholdUpdating(false);
    }
  };

  const fileList: UploadFile[] = selectedFile ? [{ uid: 'apk', name: selectedFile.name, status: 'done' }] : [];

  return (
    <div className="space-y-6">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700 shadow-sm">
              <IconApps size={24} />
            </div>
            <div>
              <h1 className="m-0 text-fluid-xl font-semibold text-slate-900">应用升级</h1>
              <p className="m-0 mt-1 max-w-2xl text-fluid-sm leading-relaxed text-slate-500">
                平台超级管理员统一发布 Android APK。公司管理员和员工不会看到此页面，也无法调用发布管理接口。
              </p>
            </div>
          </div>
          <Space wrap>
            <Button icon={<IconRefresh size={18} />} loading={loading} onClick={() => void loadReleases()}>刷新</Button>
            <Button type="primary" icon={<IconUpload size={18} />} onClick={openUpload}>上传新版本</Button>
          </Space>
        </div>
      </div>

      <Card className="rounded-xl shadow-card">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Typography.Text className="text-fluid-sm text-slate-500">强制升级阈值</Typography.Text>
            <Typography.Text className="ml-2 text-fluid-xs text-slate-400">（0 表示暂不启用强制升级）</Typography.Text>
            <div className="mt-1 space-y-1">
              <Typography.Text className="block text-fluid-base text-slate-700">
                当前值：<span className="font-semibold">{threshold === 0 ? '未启用' : threshold}</span>
              </Typography.Text>
              <Typography.Text className="block text-fluid-xs text-slate-400">
                对比基准：最新上传版本号 {latestVersionCode ?? '暂无'}
              </Typography.Text>
            </div>
          </div>
          <Space.Compact className="w-full sm:w-auto">
            <InputNumber
              min={0}
              max={latestVersionCode ?? undefined}
              precision={0}
              className="w-full sm:w-48"
              value={thresholdDraft}
              disabled={latestVersionCode == null}
              onChange={(value) => setThresholdDraft(value ?? 0)}
            />
            <Button
              type="primary"
              loading={thresholdUpdating}
              disabled={latestVersionCode == null || thresholdDraft === threshold}
              onClick={() => void handleThresholdConfirm()}
            >
              确定
            </Button>
          </Space.Compact>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="rounded-xl shadow-card lg:col-span-2">
          <div className="flex items-start gap-3">
            <IconCircleCheck size={24} className="mt-1 flex-shrink-0 text-brand-700" />
            <div className="min-w-0">
              <Typography.Text className="text-fluid-sm text-slate-500">当前生效版本</Typography.Text>
              <div className="mt-1 flex flex-wrap items-baseline gap-2">
                <span className="text-fluid-stat font-semibold text-slate-900">{activeRelease?.versionName ?? '暂无'}</span>
                {activeRelease ? <Tag color="success">versionCode {activeRelease.versionCode}</Tag> : <Tag>未发布</Tag>}
              </div>
              {activeRelease ? (
                <p className="m-0 mt-2 break-all text-fluid-xs font-mono text-slate-500">{activeRelease.fileName}</p>
              ) : null}
            </div>
          </div>
        </Card>
        <Card className="rounded-xl shadow-card">
          <Typography.Text className="text-fluid-sm text-slate-500">发布记录</Typography.Text>
          <div className="mt-1 text-fluid-stat font-semibold text-slate-900">{releases.length}</div>
          <Typography.Text className="text-fluid-xs text-slate-400">已发布记录不可替换或删除</Typography.Text>
        </Card>
      </div>

      <Card className="rounded-xl shadow-card" title={<span className="page-section-title">发布记录</span>}>
        <Table<AppReleaseRecord>
          rowKey="releaseId"
          loading={loading}
          dataSource={releases}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 1180 }}
          columns={[
            {
              title: '版本',
              key: 'version',
              width: 150,
              render: (_, record) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong className="text-fluid-base">{record.versionName}</Typography.Text>
                  <Typography.Text className="text-fluid-xs font-mono text-slate-400">{record.versionCode}</Typography.Text>
                </Space>
              ),
            },
            {
              title: 'APK 文件',
              dataIndex: 'fileName',
              width: 320,
              render: (value, record) => (
                <Space direction="vertical" size={0}>
                  <a href={record.downloadUrl} className="text-fluid-sm text-brand-700" target="_blank" rel="noreferrer">{value}</a>
                  <Typography.Text className="text-fluid-xs text-slate-400">{formatFileSize(record.fileSize)}</Typography.Text>
                </Space>
              ),
            },
            {
              title: 'SHA-256',
              dataIndex: 'sha256',
              width: 220,
              ellipsis: true,
              render: (value) => <Typography.Text copyable className="text-fluid-xs font-mono">{value}</Typography.Text>,
            },
            {
              title: '强制阈值',
              dataIndex: 'forceUpgradeVersionCode',
              width: 120,
              render: (value) => value === 0 ? <Tag>未启用</Tag> : <Tag color="warning">{value}</Tag>,
            },
            {
              title: '上传信息',
              key: 'created',
              width: 190,
              render: (_, record) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text className="text-fluid-sm">{record.createdBy || '-'}</Typography.Text>
                  <Typography.Text className="text-fluid-xs text-slate-400">{formatDateTime(record.createdAt)}</Typography.Text>
                </Space>
              ),
            },
            {
              title: '状态',
              dataIndex: 'isActive',
              fixed: 'right',
              width: 110,
              render: (_, record) => (
                <Switch
                  checked={record.isActive}
                  checkedChildren="启用"
                  unCheckedChildren="停用"
                  loading={changingReleaseId === record.releaseId}
                  onChange={(checked) => void handleActiveChange(record, checked)}
                />
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="上传 Android 新版本"
        open={uploadOpen}
        width="min(92vw, 680px)"
        okText="上传并发布"
        cancelText="取消"
        confirmLoading={uploading}
        maskClosable={!uploading}
        closable={!uploading}
        onCancel={() => setUploadOpen(false)}
        onOk={() => void handleUpload()}
      >
        <Form<ReleaseFormValues> form={form} layout="vertical" disabled={uploading} className="mt-5">
          <Form.Item label="APK 文件" required extra="文件名必须与完整版本标识一致，例如 solin_cloud_1.0.2_20260720_1030.apk">
            <Upload.Dragger
              accept=".apk,application/vnd.android.package-archive"
              maxCount={1}
              fileList={fileList}
              beforeUpload={(file) => {
                if (!file.name.toLowerCase().endsWith('.apk')) {
                  message.error('仅支持 .apk 文件');
                  return Upload.LIST_IGNORE;
                }
                setSelectedFile(file);
                form.setFieldValue('versionInfo', file.name.slice(0, -4));
                return Upload.LIST_IGNORE;
              }}
              onRemove={() => {
                setSelectedFile(null);
                return true;
              }}
            >
              <IconFileText size={32} className="mx-auto mb-2 text-brand-700" />
              <p className="m-0 text-fluid-base font-medium text-slate-700">拖拽 APK 到此处，或点击选择</p>
              <p className="m-0 mt-1 text-fluid-xs text-slate-400">上传后由后台计算文件大小和 SHA-256</p>
            </Upload.Dragger>
          </Form.Item>
          <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
            <Form.Item name="versionName" label="版本名称" rules={[{ required: true, message: '请输入版本名称' }]}>
              <Input placeholder="1.0.2" />
            </Form.Item>
            <Form.Item name="versionCode" label="内部版本号" rules={[{ required: true, message: '请输入内部版本号' }]}>
              <InputNumber min={1} precision={0} className="w-full" placeholder="10002" />
            </Form.Item>
          </div>
          <Form.Item name="versionInfo" label="完整版本标识" rules={[{ required: true, message: '请输入完整版本标识' }]}>
            <Input placeholder="solin_cloud_1.0.2_20260720_1030" />
          </Form.Item>
          <Form.Item name="releaseNotes" label="更新说明">
            <Input.TextArea rows={4} maxLength={2000} showCount placeholder="填写本次更新内容" />
          </Form.Item>
          <Form.Item name="isActive" label="上传后立即启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          {uploading ? <Progress percent={uploadProgress} status="active" /> : null}
        </Form>
      </Modal>
    </div>
  );
};
