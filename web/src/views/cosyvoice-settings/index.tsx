import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  IconArrowLeft,
  IconDeviceFloppy,
  IconHeadphones,
  IconRefresh,
  IconTrash,
  IconVolume,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
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

type SettingsFormValues = {
  apiKey?: string;
  websocketUrl: string;
  customizationUrl: string;
  isActive: boolean;
  defaultVoiceId: number | null;
  defaultTestText: string;
};

type EnrollFormValues = { displayName: string; sourceAudioUrl: string; avatarPath?: string };
type DesignFormValues = { displayName: string; description: string; language: 'zh' | 'en'; avatarPath?: string };

const AVATAR_OPTIONS = [
  ...['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight'].map((name) => ({ label: `女声头像 ${name}`, value: `/static/tts/voices/voice_female_${name}.png` })),
  ...['one', 'two', 'three', 'four', 'five', 'six'].map((name) => ({ label: `男声头像 ${name}`, value: `/static/tts/voices/voice_male_${name}.png` })),
];

const playBlob = (blob: Blob) => {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
  void audio.play();
};

export const CosyVoiceSettingsPage = () => {
  const navigate = useNavigate();
  const [settingsForm] = Form.useForm<SettingsFormValues>();
  const [enrollForm] = Form.useForm<EnrollFormValues>();
  const [designForm] = Form.useForm<DesignFormValues>();
  const [settings, setSettings] = useState<CosyVoiceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [designOpen, setDesignOpen] = useState(false);

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

  const createEnrollment = async () => {
    const values = await enrollForm.validateFields();
    try {
      await enrollCosyVoice(values);
      setEnrollOpen(false);
      enrollForm.resetFields();
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

  const columns: ColumnsType<CosyVoiceVoiceRecord> = [
    { title: '名称', dataIndex: 'displayName', key: 'displayName', render: (value) => <span className="text-fluid-base">{value}</span> },
    { title: '音色 ID', dataIndex: 'voiceCode', key: 'voiceCode', render: (value) => <span className="text-fluid-xs font-mono">{value}</span> },
    { title: '来源', key: 'source', render: (_, voice) => <span className="text-fluid-sm">{voice.sourceType === 'design' ? '设计' : '复刻'}{voice.language ? ` · ${voice.language}` : ''}</span> },
    { title: '默认', key: 'default', render: (_, voice) => <Switch checked={voice.isDefault} onChange={(isDefault) => void updateCosyVoiceVoice(voice.id, { isDefault }).then(load).catch(() => message.error('默认音色更新失败'))} /> },
    { title: '启用', key: 'active', render: (_, voice) => <Switch checked={voice.isActive} onChange={(isActive) => void updateCosyVoiceVoice(voice.id, { isActive }).then(load).catch(() => message.error('音色状态更新失败'))} /> },
    {
      title: '操作',
      key: 'actions',
      render: (_, voice) => (
        <Space wrap>
          <Button type="text" icon={<IconVolume size={16} />} onClick={() => void testVoice(voice)}>试听</Button>
          <Popconfirm title="删除后将同步删除远程 CosyVoice 音色。" onConfirm={() => void deleteCosyVoiceVoice(voice.id).then(load).catch(() => message.error('音色删除失败'))}>
            <Button type="text" danger icon={<IconTrash size={16} />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="container py-6">
      <div className="page-hero mb-6">
        <div>
          <Typography.Title level={2} className="text-fluid-xl">CosyVoice v3.5-plus</Typography.Title>
          <Typography.Paragraph className="text-fluid-base mb-0">独立管理定制音色；仅支持复刻或设计创建的 CosyVoice 音色。</Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<IconArrowLeft size={16} />} onClick={() => navigate('/settings/tts')}>返回供应商</Button>
          <Button icon={<IconRefresh size={16} />} loading={loading} onClick={() => void load()}>刷新</Button>
        </Space>
      </div>

      <Card className="rounded-xl shadow-card mb-6" loading={loading} title={<span className="text-fluid-lg">服务配置</span>}>
        <Form form={settingsForm} layout="vertical" onFinish={save}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Form.Item label="启用 CosyVoice" name="isActive" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item label="API Key" name="apiKey" extra={settings?.apiKeyConfigured ? `已配置：${settings.apiKeyMasked}；请填写在阿里云百炼 Model Studio 控制台「API Key」页面创建的华北2（北京）API Key（如 sk-... 或 sk-sp-...）；留空保持不变。` : '请填写在阿里云百炼 Model Studio 控制台「API Key」页面创建的华北2（北京）API Key（如 sk-... 或 sk-sp-...）。留空表示尚未配置。'}><Input.Password autoComplete="new-password" placeholder="sk-..." /></Form.Item>
            <Form.Item label="WebSocket 地址" name="websocketUrl" rules={[{ required: true, message: '请填写 WebSocket 地址' }]} extra="CosyVoice 实时 WSS 地址，仅接受 wss://。北京用户请在阿里云百炼工作空间的 CosyVoice 控制台或官方文档中复制实时端点；将 {WorkspaceId} 替换为百炼工作空间 ID。请勿填写下方单独配置的 HTTPS 音色定制 API 地址。"><Input placeholder="wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference" /></Form.Item>
            <Form.Item label="音色定制 API 地址" name="customizationUrl" rules={[{ required: true, message: '请填写音色定制 API 地址' }]}><Input placeholder="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization" /></Form.Item>
            <Form.Item label="默认音色" name="defaultVoiceId"><Select allowClear options={settings?.voices.map((voice) => ({ label: voice.displayName, value: voice.id })) ?? []} /></Form.Item>
            <Form.Item label="模型"><Input disabled value="cosyvoice-v3.5-plus" /></Form.Item>
          </div>
          <Form.Item label="试听文本" name="defaultTestText" rules={[{ required: true, message: '请填写试听文本' }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={saving} icon={<IconDeviceFloppy size={16} />}>保存配置</Button>
        </Form>
      </Card>

      <Card className="rounded-xl shadow-card" title={<span className="text-fluid-lg">自定义音色</span>} extra={<Space wrap><Button icon={<IconHeadphones size={16} />} onClick={() => setEnrollOpen(true)}>复刻音色</Button><Button type="primary" icon={<IconDeviceFloppy size={16} />} onClick={() => setDesignOpen(true)}>设计音色</Button></Space>}>
        <Table rowKey="id" columns={columns} dataSource={settings?.voices ?? []} pagination={false} scroll={{ x: 860 }} />
      </Card>

      <Modal title="复刻 CosyVoice 音色" open={enrollOpen} onCancel={() => setEnrollOpen(false)} onOk={() => void createEnrollment()} okText="提交复刻">
        <Form form={enrollForm} layout="vertical"><Form.Item label="名称" name="displayName" rules={[{ required: true, message: '请填写名称' }]}><Input /></Form.Item><Form.Item label="参考音频 HTTPS URL" name="sourceAudioUrl" rules={[{ required: true, type: 'url', message: '请填写有效 HTTPS URL' }, { pattern: /^https:\/\//, message: '必须使用 HTTPS URL' }]}><Input placeholder="https://…" /></Form.Item><Form.Item label="头像（可选）" name="avatarPath"><Select allowClear options={AVATAR_OPTIONS} /></Form.Item></Form>
      </Modal>
      <Modal title="设计 CosyVoice 音色" open={designOpen} onCancel={() => setDesignOpen(false)} onOk={() => void createDesign()} okText="提交设计">
        <Form form={designForm} layout="vertical" initialValues={{ language: 'zh' }}><Form.Item label="名称" name="displayName" rules={[{ required: true, message: '请填写名称' }]}><Input /></Form.Item><Form.Item label="语言" name="language" rules={[{ required: true }]}><Select options={[{ label: '中文', value: 'zh' }, { label: 'English', value: 'en' }]} /></Form.Item><Form.Item label="音色描述" name="description" rules={[{ required: true, message: '请填写描述' }]}><Input.TextArea rows={4} maxLength={2000} /></Form.Item><Form.Item label="头像（可选）" name="avatarPath"><Select allowClear options={AVATAR_OPTIONS} /></Form.Item></Form>
      </Modal>
    </div>
  );
};
