import { useCallback, useEffect, useState } from 'react';
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
  Switch,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  IconArrowLeft,
  IconDeviceFloppy,
  IconEdit,
  IconHeadphones,
  IconPhotoEdit,
  IconRefresh,
  IconTrash,
  IconUpload,
  IconVolume,
  IconZoomIn,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { normalizeMediaAssetUrl } from '../../api/client';
import {
  deleteCosyVoiceVoice,
  designCosyVoice,
  enrollCosyVoice,
  fetchCosyVoiceSettings,
  testCosyVoice,
  updateCosyVoiceSettings,
  updateCosyVoiceVoice,
  type CosyVoiceSettings,
  type CosyVoiceVoiceRecord,
} from '../../api/modules/cosyvoice';
import { StatusTag } from '../../components/status-tag';

type SettingsFormValues = {
  apiKey?: string;
  websocketUrl: string;
  customizationUrl: string;
  isActive: boolean;
  defaultVoiceId: number | null;
  defaultTestText: string;
};

type EnrollFormValues = { displayName: string; sourceAudioUrl: string };
type DesignFormValues = { displayName: string; description: string; language: 'zh' | 'en' };

type EditFormValues = {
  displayName: string;
  isActive: boolean;
  isDefault: boolean;
};

const playBlob = (blob: Blob) => {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
  void audio.play();
};

const avatarSrcOf = (voice: CosyVoiceVoiceRecord) =>
  voice.avatarPath ? normalizeMediaAssetUrl(voice.avatarPath) : '';

const VOICE_AVATAR_ACCEPT = 'image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp';
const VOICE_AVATAR_MIME_TYPES: Record<string, true> = {
  'image/png': true,
  'image/jpeg': true,
  'image/jpg': true,
  'image/webp': true,
};
const VOICE_AVATAR_EXTENSIONS: Record<string, true> = {
  '.png': true,
  '.jpg': true,
  '.jpeg': true,
  '.webp': true,
};

const isAllowedVoiceAvatarFile = (file: File) => {
  const mimeOk = !file.type || Boolean(VOICE_AVATAR_MIME_TYPES[file.type.toLowerCase()]);
  const name = file.name || '';
  const dot = name.lastIndexOf('.');
  const ext = dot >= 0 ? name.slice(dot).toLowerCase() : '';
  const extOk = !ext || Boolean(VOICE_AVATAR_EXTENSIONS[ext]);
  return mimeOk && extOk && (Boolean(file.type) || Boolean(ext));
};

export const CosyVoiceSettingsPage = () => {
  const navigate = useNavigate();
  const [settingsForm] = Form.useForm<SettingsFormValues>();
  const [enrollForm] = Form.useForm<EnrollFormValues>();
  const [designForm] = Form.useForm<DesignFormValues>();
  const [editForm] = Form.useForm<EditFormValues>();
  const [settings, setSettings] = useState<CosyVoiceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [designOpen, setDesignOpen] = useState(false);
  const [previewVoice, setPreviewVoice] = useState<CosyVoiceVoiceRecord | null>(null);
  const [editVoice, setEditVoice] = useState<CosyVoiceVoiceRecord | null>(null);
  const [avatarVoice, setAvatarVoice] = useState<CosyVoiceVoiceRecord | null>(null);
  const [avatarFileList, setAvatarFileList] = useState<UploadFile[]>([]);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [enrollAvatarFileList, setEnrollAvatarFileList] = useState<UploadFile[]>([]);
  const [enrollAvatarPreviewUrl, setEnrollAvatarPreviewUrl] = useState('');


  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await fetchCosyVoiceSettings();
      setSettings(next);
      settingsForm.setFieldsValue({
        websocketUrl: next.websocketUrl,
        customizationUrl: next.customizationUrl,
        isActive: next.isActive,
        defaultVoiceId: next.defaultVoiceId,
        defaultTestText: next.defaultTestText,
      });
    } catch {
      message.error('CosyVoice 配置加载失败');
    } finally {
      setLoading(false);
    }
  }, [settingsForm]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    return () => {
      if (avatarPreviewUrl) URL.revokeObjectURL(avatarPreviewUrl);
    };
  }, [avatarPreviewUrl]);

  useEffect(() => {
    return () => {
      if (enrollAvatarPreviewUrl) URL.revokeObjectURL(enrollAvatarPreviewUrl);
    };
  }, [enrollAvatarPreviewUrl]);


  const save = async (values: SettingsFormValues) => {
    setSaving(true);
    try {
      const next = await updateCosyVoiceSettings(values);
      setSettings(next);
      settingsForm.setFieldsValue({ ...values, apiKey: undefined });
      message.success('CosyVoice 设置已保存');
    } catch {
      message.error('CosyVoice 设置保存失败');
    } finally {
      setSaving(false);
    }
  };

  const resetEnrollAvatar = () => {
    setEnrollAvatarFileList([]);
    if (enrollAvatarPreviewUrl) URL.revokeObjectURL(enrollAvatarPreviewUrl);
    setEnrollAvatarPreviewUrl('');
  };

  const openEnroll = () => {
    resetEnrollAvatar();
    enrollForm.resetFields();
    setEnrollOpen(true);
  };

  const closeEnroll = () => {
    setEnrollOpen(false);
    enrollForm.resetFields();
    resetEnrollAvatar();
  };

  const createEnrollment = async () => {
    const values = await enrollForm.validateFields();
    const raw = enrollAvatarFileList[0];
    const file = (raw?.originFileObj ?? (raw as UploadFile & { file?: File })?.file) as File | undefined;
    try {
      await enrollCosyVoice({
        ...values,
        ...(file ? { avatar: file } : {}),
      });
      closeEnroll();
      message.success('音色复刻请求已创建');
      await load();
    } catch {
      message.error('音色复刻失败，请检查上游配置和参考音频 URL');
    }
  };

  const createDesign = async () => {
    const values = await designForm.validateFields();
    try {
      await designCosyVoice(values);
      setDesignOpen(false);
      designForm.resetFields();
      message.success('音色设计请求已创建');
      await load();
    } catch {
      message.error('音色设计失败，请检查上游配置');
    }
  };

  const testVoice = async (voice: CosyVoiceVoiceRecord) => {
    try {
      playBlob(await testCosyVoice({ voiceId: voice.id, text: settingsForm.getFieldValue('defaultTestText') }));
    } catch {
      message.error('音色试听失败');
    }
  };

  const openEdit = (voice: CosyVoiceVoiceRecord) => {
    setEditVoice(voice);
    editForm.setFieldsValue({
      displayName: voice.displayName,
      isActive: voice.isActive,
      isDefault: voice.isDefault,
    });
  };

  const saveEdit = async () => {
    if (!editVoice) return;
    const values = await editForm.validateFields();
    setEditSaving(true);
    try {
      await updateCosyVoiceVoice(editVoice.id, values);
      message.success('音色已更新');
      setEditVoice(null);
      await load();
    } catch {
      message.error('音色更新失败');
    } finally {
      setEditSaving(false);
    }
  };

  const openAvatarChange = (voice: CosyVoiceVoiceRecord) => {
    setPreviewVoice(null);
    setAvatarVoice(voice);
    setAvatarFileList([]);
    if (avatarPreviewUrl) URL.revokeObjectURL(avatarPreviewUrl);
    setAvatarPreviewUrl('');
  };

  const closeAvatarChange = () => {
    setAvatarVoice(null);
    setAvatarFileList([]);
    if (avatarPreviewUrl) URL.revokeObjectURL(avatarPreviewUrl);
    setAvatarPreviewUrl('');
  };

  const saveAvatar = async () => {
    if (!avatarVoice) return;
    const raw = avatarFileList[0];
    const file = (raw?.originFileObj ?? (raw as UploadFile & { file?: File })?.file) as File | undefined;
    if (!file) {
      message.error('请先选择本地图片');
      return;
    }
    setAvatarSaving(true);
    try {
      await updateCosyVoiceVoice(avatarVoice.id, { avatar: file });
      message.success('音色头像已更新');
      closeAvatarChange();
      await load();
    } catch {
      message.error('音色头像上传失败');
    } finally {
      setAvatarSaving(false);
    }
  };


  const voices = settings?.voices ?? [];

  return (
    <div className="container py-6">
      <div className="page-hero mb-6">
        <div>
          <Typography.Title level={2} className="text-fluid-xl">
            CosyVoice v3.5-plus
          </Typography.Title>
          <Typography.Paragraph className="text-fluid-base mb-0">
            以头像卡片管理定制音色；支持本地上传更换音色头像，并预览大图。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<IconArrowLeft size={16} />} onClick={() => navigate('/settings/tts')}>
            返回供应商
          </Button>
          <Button icon={<IconRefresh size={16} />} loading={loading} onClick={() => void load()}>
            刷新
          </Button>
        </Space>
      </div>

      <Card className="mb-6 rounded-xl shadow-card" loading={loading} title={<span className="text-fluid-lg">服务配置</span>}>
        <Form form={settingsForm} layout="vertical" onFinish={save}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Form.Item label="启用 CosyVoice" name="isActive" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              label="API Key"
              name="apiKey"
              extra={
                settings?.apiKeyConfigured
                  ? `已配置：${settings.apiKeyMasked}；请填写在阿里云百炼 Model Studio 控制台「API Key」页面创建的华北2（北京）API Key（如 sk-... 或 sk-sp-...）；留空保持不变。`
                  : '请填写在阿里云百炼 Model Studio 控制台「API Key」页面创建的华北2（北京）API Key（如 sk-... 或 sk-sp-...）。留空表示尚未配置。'
              }
            >
              <Input.Password autoComplete="new-password" placeholder="sk-..." />
            </Form.Item>
            <Form.Item
              label="WebSocket 地址"
              name="websocketUrl"
              rules={[{ required: true, message: '请填写 WebSocket 地址' }]}
              extra="CosyVoice 实时 WSS 地址，仅接受 wss://。北京用户请在阿里云百炼工作空间的 CosyVoice 控制台或官方文档中复制实时端点；将 {WorkspaceId} 替换为百炼工作空间 ID。请勿填写下方单独配置的 HTTPS 音色定制 API 地址。"
            >
              <Input placeholder="wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference" />
            </Form.Item>
            <Form.Item
              label="音色定制 API 地址"
              name="customizationUrl"
              rules={[{ required: true, message: '请填写音色定制 API 地址' }]}
            >
              <Input placeholder="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization" />
            </Form.Item>
            <Form.Item label="默认音色" name="defaultVoiceId">
              <Select allowClear options={voices.map((voice) => ({ label: voice.displayName, value: voice.id }))} />
            </Form.Item>
            <Form.Item label="模型">
              <Input disabled value="cosyvoice-v3.5-plus" />
            </Form.Item>
          </div>
          <Form.Item label="试听文本" name="defaultTestText" rules={[{ required: true, message: '请填写试听文本' }]}>
            <Input.TextArea rows={3} maxLength={2000} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving} icon={<IconDeviceFloppy size={16} />}>
            保存配置
          </Button>
        </Form>
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="page-section-title">自定义音色</div>
          <div className="mt-1 text-fluid-sm text-slate-500">
            {settings ? (
              <>
                <StatusTag
                  type={settings.isActive ? 'active' : 'inactive'}
                  label={settings.isActive ? '服务启用' : '服务停用'}
                />
                <span className="ml-2">{voices.length} 个音色</span>
              </>
            ) : null}
          </div>
        </div>
        <Space wrap>
          <Button icon={<IconHeadphones size={16} />} onClick={openEnroll}>
            复刻音色
          </Button>
          <Button type="primary" icon={<IconDeviceFloppy size={16} />} onClick={() => setDesignOpen(true)}>
            设计音色
          </Button>
        </Space>
      </div>

      {!loading && voices.length === 0 ? (
        <Card className="rounded-xl shadow-card">
          <Empty description="暂无自定义音色" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {voices.map((voice) => {
            const src = avatarSrcOf(voice);
            return (
              <Card
                key={voice.id}
                loading={loading}
                className="overflow-hidden rounded-2xl border border-slate-200/70 shadow-card transition hover:border-brand-300 hover:shadow-card-hover"
                styles={{ body: { padding: 0 } }}
              >
                <div className="relative bg-gradient-to-br from-brand-50 via-white to-slate-50 px-5 pb-4 pt-6">
                  <button type="button" className="group relative mx-auto block" onClick={() => setPreviewVoice(voice)}>
                    {src ? (
                      <img
                        src={src}
                        alt={voice.displayName}
                        className="h-28 w-28 rounded-full object-cover shadow-lg ring-4 ring-white"
                      />
                    ) : (
                      <div className="flex h-28 w-28 items-center justify-center rounded-full bg-white text-brand-600 shadow-lg ring-4 ring-white">
                        <IconHeadphones size={36} />
                      </div>
                    )}
                    <span className="absolute inset-0 flex items-center justify-center rounded-full bg-slate-900/0 text-white opacity-0 transition group-hover:bg-slate-900/40 group-hover:opacity-100">
                      <IconZoomIn size={22} />
                    </span>
                  </button>
                  <div className="mt-4 text-center">
                    <div className="truncate text-fluid-lg text-slate-900">{voice.displayName}</div>
                    <div className="mt-1 truncate text-fluid-xs font-mono text-slate-400">{voice.voiceCode}</div>
                    <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                      {voice.isDefault ? (
                        <Tag color="success" className="m-0">
                          默认
                        </Tag>
                      ) : null}
                      <StatusTag type={voice.isActive ? 'active' : 'inactive'} />
                      <Tag className="m-0">{voice.sourceType === 'design' ? '设计' : '复刻'}</Tag>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 border-t border-slate-100 p-3">
                  <Button
                    type="primary"
                    block
                    size="middle"
                    icon={<IconPhotoEdit size={16} />}
                    onClick={() => openAvatarChange(voice)}
                  >
                    换头像
                  </Button>
                  <Button block size="middle" icon={<IconVolume size={16} />} onClick={() => void testVoice(voice)}>
                    试听
                  </Button>
                  <Button block size="middle" icon={<IconEdit size={16} />} onClick={() => openEdit(voice)}>
                    编辑
                  </Button>
                  <Popconfirm
                    title="删除后将同步删除远程 CosyVoice 音色。"
                    onConfirm={() =>
                      void deleteCosyVoiceVoice(voice.id)
                        .then(load)
                        .catch(() => message.error('音色删除失败'))
                    }
                  >
                    <Button block danger size="middle" icon={<IconTrash size={16} />}>
                      删除
                    </Button>
                  </Popconfirm>
                </div>

              </Card>
            );
          })}
        </div>
      )}

      <Modal
        title={previewVoice?.displayName || '头像预览'}
        open={!!previewVoice}
        onCancel={() => setPreviewVoice(null)}
        footer={
          previewVoice ? (
            <Button type="primary" block icon={<IconPhotoEdit size={16} />} onClick={() => openAvatarChange(previewVoice)}>
              更换此音色头像
            </Button>
          ) : null
        }
        width={Math.min(520, typeof window !== 'undefined' ? window.innerWidth - 32 : 520)}
        destroyOnHidden

      >
        {previewVoice ? (
          <div className="flex flex-col items-center gap-3 py-2">
            {avatarSrcOf(previewVoice) ? (
              <img
                src={avatarSrcOf(previewVoice)}
                alt={previewVoice.displayName}
                className="max-h-[60vh] w-full rounded-2xl object-contain"
              />
            ) : (
              <div className="flex h-48 w-48 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                <IconHeadphones size={48} />
              </div>
            )}
            <div className="text-fluid-xs font-mono text-slate-400">{previewVoice.voiceCode}</div>
          </div>
        ) : null}
      </Modal>

      <Modal
        title={avatarVoice ? `更换头像 · ${avatarVoice.displayName}` : '更换头像'}
        open={!!avatarVoice}
        onCancel={closeAvatarChange}
        onOk={() => void saveAvatar()}
        okText="上传并保存"
        confirmLoading={avatarSaving}
        destroyOnHidden
        width={Math.min(480, typeof window !== 'undefined' ? window.innerWidth - 32 : 480)}
      >
        {avatarVoice ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
              {avatarPreviewUrl || avatarSrcOf(avatarVoice) ? (
                <img
                  src={avatarPreviewUrl || avatarSrcOf(avatarVoice)}
                  alt={avatarVoice.displayName}
                  className="h-16 w-16 rounded-full object-cover ring-2 ring-white"
                />
              ) : (
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-brand-600 ring-2 ring-white">
                  <IconHeadphones size={28} />
                </div>
              )}
              <div className="min-w-0">
                <div className="truncate text-fluid-base font-medium text-slate-800">{avatarVoice.displayName}</div>
                <div className="text-fluid-sm text-slate-500">仅支持本地上传 PNG / JPEG / WebP</div>
              </div>
            </div>
            <Upload.Dragger
              accept={VOICE_AVATAR_ACCEPT}
              maxCount={1}
              fileList={avatarFileList}
              beforeUpload={(file) => {
                if (!isAllowedVoiceAvatarFile(file)) {
                  message.error('仅支持 PNG / JPEG / WebP 图片');
                  return Upload.LIST_IGNORE;
                }
                return false;
              }}
              onChange={({ fileList }) => {
                const next = fileList.slice(-1);
                setAvatarFileList(next);
                const file = next[0]?.originFileObj;
                if (avatarPreviewUrl) URL.revokeObjectURL(avatarPreviewUrl);
                setAvatarPreviewUrl(file ? URL.createObjectURL(file) : '');
              }}
              className="rounded-xl"
            >
              <p className="flex justify-center text-brand-600">
                <IconUpload size={28} />
              </p>
              <p className="text-fluid-sm text-slate-700">点击或拖拽本地图片到此处</p>
              <p className="text-fluid-xs text-slate-400">上传后保存，将作为该音色头像</p>
            </Upload.Dragger>
          </div>
        ) : null}
      </Modal>

      <Modal
        title="编辑音色"
        open={!!editVoice}
        onCancel={() => setEditVoice(null)}
        onOk={() => void saveEdit()}
        okText="保存"
        confirmLoading={editSaving}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="显示名称" name="displayName" rules={[{ required: true, message: '请填写名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item label="启用" name="isActive" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
          <Form.Item label="设为默认" name="isDefault" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="复刻 CosyVoice 音色"
        open={enrollOpen}
        onCancel={closeEnroll}
        onOk={() => void createEnrollment()}
        okText="提交复刻"
        destroyOnHidden
      >
        <Form form={enrollForm} layout="vertical">
          <Form.Item label="名称" name="displayName" rules={[{ required: true, message: '请填写名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            label="参考音频 HTTPS URL"
            name="sourceAudioUrl"
            rules={[
              { required: true, type: 'url', message: '请填写有效 HTTPS URL' },
              { pattern: /^https:\/\//, message: '必须使用 HTTPS URL' },
            ]}
          >
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item label="音色头像（可选）">
            <div className="space-y-3">
              {enrollAvatarPreviewUrl ? (
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
                  <img
                    src={enrollAvatarPreviewUrl}
                    alt="头像预览"
                    className="h-14 w-14 rounded-full object-cover ring-2 ring-white"
                  />
                  <div className="text-fluid-sm text-slate-500">已选择本地图片，提交复刻时一并上传</div>
                </div>
              ) : null}
              <Upload.Dragger
                accept={VOICE_AVATAR_ACCEPT}
                maxCount={1}
                fileList={enrollAvatarFileList}
                beforeUpload={(file) => {
                  if (!isAllowedVoiceAvatarFile(file)) {
                    message.error('仅支持 PNG / JPEG / WebP 图片');
                    return Upload.LIST_IGNORE;
                  }
                  return false;
                }}
                onChange={({ fileList }) => {
                  const next = fileList.slice(-1);
                  setEnrollAvatarFileList(next);
                  const file = next[0]?.originFileObj;
                  if (enrollAvatarPreviewUrl) URL.revokeObjectURL(enrollAvatarPreviewUrl);
                  setEnrollAvatarPreviewUrl(file ? URL.createObjectURL(file) : '');
                }}
                className="rounded-xl"
              >
                <p className="flex justify-center text-brand-600">
                  <IconUpload size={28} />
                </p>
                <p className="text-fluid-sm text-slate-700">点击或拖拽本地图片到此处</p>
                <p className="text-fluid-xs text-slate-400">可选；仅支持 PNG / JPEG / WebP</p>
              </Upload.Dragger>
            </div>
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="设计 CosyVoice 音色" open={designOpen} onCancel={() => setDesignOpen(false)} onOk={() => void createDesign()} okText="提交设计">
        <Form form={designForm} layout="vertical" initialValues={{ language: 'zh' }}>
          <Form.Item label="名称" name="displayName" rules={[{ required: true, message: '请填写名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="语言" name="language" rules={[{ required: true }]}>
            <Select options={[{ label: '中文', value: 'zh' }, { label: 'English', value: 'en' }]} />
          </Form.Item>
          <Form.Item label="音色描述" name="description" rules={[{ required: true, message: '请填写描述' }]}>
            <Input.TextArea rows={4} maxLength={2000} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
