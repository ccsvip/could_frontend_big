import {
  ApiOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Button, Form, Input, Modal, Typography, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import heroLayerImage from '../../assets/hero.png';
import { applyAccountRequest, loginRequest } from '../../api/modules/auth';
import { BrandMark } from '../../components/brand-mark';
import { useAuthStore } from '../../store/auth';

const APP_TITLE = import.meta.env.VITE_APP_TITLE || '数字人后台管理平台';

type LoginForm = {
  username: string;
  password: string;
};

type ApplyAccountForm = {
  username: string;
  applicantName: string;
  phone: string;
  email?: string;
  reason: string;
};

const systemNodes = [
  { label: '设备', icon: <CloudServerOutlined />, className: 'left-8 top-12', delay: '0s' },
  { label: '模型', icon: <DatabaseOutlined />, className: 'right-10 top-20', delay: '0.4s' },
  { label: '权限', icon: <SafetyCertificateOutlined />, className: 'left-16 bottom-12', delay: '0.8s' },
  { label: '接口', icon: <ApiOutlined />, className: 'right-20 bottom-10', delay: '1.2s' },
];

export const LoginPage = () => {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const [applyVisible, setApplyVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applyForm] = Form.useForm<ApplyAccountForm>();

  const onSubmit = async (values: LoginForm) => {
    setSubmitting(true);
    try {
      const response = await loginRequest(values);
      login({
        username: response.user.display_name || response.user.username,
        token: response.access,
        refreshToken: response.refresh,
        role: response.user.role,
        permissions: response.user.permissions,
        menus: response.user.menus,
      });
      message.success(response.message || '登录成功');
      navigate('/devices', { replace: true });
    } finally {
      setSubmitting(false);
    }
  };

  const handleApplySubmit = async () => {
    const values = await applyForm.validateFields();
    setApplySubmitting(true);
    try {
      const response = await applyAccountRequest(values);
      message.success(response.message || '账号申请已提交，管理员会尽快审核');
      setApplyVisible(false);
      applyForm.resetFields();
    } catch {
      // 错误已在拦截器中处理
    } finally {
      setApplySubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#eef3f1] text-slate-900">
      <style>
        {`
          @keyframes ops-drift {
            0%, 100% { transform: translate3d(0, 0, 0); }
            50% { transform: translate3d(0, -8px, 0); }
          }

          @keyframes ops-pulse {
            0%, 100% { transform: scale(0.72); opacity: 0.4; }
            50% { transform: scale(1); opacity: 1; }
          }

          @keyframes ops-ring {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }

          @keyframes ops-flow {
            0% { stroke-dashoffset: 90; opacity: 0.3; }
            50% { opacity: 0.8; }
            100% { stroke-dashoffset: 0; opacity: 0.3; }
          }
        `}
      </style>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_14%,rgba(20,184,166,0.18),transparent_32%),radial-gradient(circle_at_84%_18%,rgba(13,148,136,0.10),transparent_30%),linear-gradient(135deg,#f8fafc_0%,#edf6f4_48%,#e8edf4_100%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.04] [background-image:linear-gradient(#0f172a_1px,transparent_1px),linear-gradient(90deg,#0f172a_1px,transparent_1px)] [background-size:42px_42px]" />

      <main className="relative z-10 flex min-h-screen flex-col px-5 py-6 sm:px-8 lg:px-12">
        <header className="mx-auto flex w-full max-w-7xl items-center justify-between">
          <BrandMark title={APP_TITLE} subtitle="后台管理" />
        </header>

        <section className="mx-auto grid w-full max-w-7xl flex-1 items-center gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-16">
          <div className="hidden min-w-0 lg:block">
            <Typography.Title className="!mb-3 !max-w-2xl !text-[48px] !font-bold !leading-[1.1] !tracking-tight !text-slate-900">
              数字人管理平台
            </Typography.Title>
            <Typography.Paragraph className="!max-w-xl !text-[15px] !text-slate-500">
              统一管理设备、模型、知识库与控制指令，让 AI 终端运营更高效、更可控。
            </Typography.Paragraph>

            {/* 左侧只做抽象后台系统动效，不展示未接入的真实业务数据。 */}
            <div className="relative mt-8 h-[400px] max-w-3xl">
              <div className="absolute inset-0 rounded-[28px] border border-white/80 bg-white/40 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur" />
              <div className="absolute inset-5 overflow-hidden rounded-[22px] bg-slate-950">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_28%_30%,rgba(45,212,191,0.22),transparent_34%),radial-gradient(circle_at_78%_70%,rgba(13,148,136,0.16),transparent_32%)]" />
                <div className="absolute inset-0 opacity-[0.10] [background-image:linear-gradient(#ffffff_1px,transparent_1px),linear-gradient(90deg,#ffffff_1px,transparent_1px)] [background-size:36px_36px]" />

                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 720 360" aria-hidden="true">
                  <path d="M150 98 C260 38 420 36 560 118" fill="none" stroke="rgba(94,234,212,0.30)" strokeWidth="1.5" strokeDasharray="10 12" style={{ animation: 'ops-flow 7s linear infinite' }} />
                  <path d="M164 252 C286 318 448 316 560 238" fill="none" stroke="rgba(94,234,212,0.20)" strokeWidth="1.5" strokeDasharray="8 14" style={{ animation: 'ops-flow 8s linear reverse infinite' }} />
                  <path d="M180 174 H542" fill="none" stroke="rgba(148,163,184,0.20)" strokeWidth="1" strokeDasharray="6 12" style={{ animation: 'ops-flow 9s linear infinite' }} />
                </svg>

                <div className="absolute left-1/2 top-1/2 flex h-40 w-40 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[24px] border border-white/10 bg-white/[0.04]">
                  <div className="absolute h-60 w-60 rounded-full border border-teal-300/16" style={{ animation: 'ops-ring 22s linear infinite' }} />
                  <div className="absolute h-40 w-40 rounded-full border border-teal-300/12" style={{ animation: 'ops-ring 16s linear reverse infinite' }} />
                  <img src={heroLayerImage} alt="" className="relative z-10 w-28 drop-shadow-[0_18px_30px_rgba(45,212,191,0.20)]" />
                </div>

                {systemNodes.map((item) => (
                  <div
                    key={item.label}
                    className={`absolute flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] px-2.5 py-1.5 text-[12px] font-medium text-slate-100 backdrop-blur ${item.className}`}
                    style={{ animation: `ops-drift 6s ease-in-out ${item.delay} infinite` }}
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/8 text-teal-300">
                      {item.icon}
                    </span>
                    {item.label}
                    <span className="h-1.5 w-1.5 rounded-full bg-teal-300" style={{ animation: `ops-pulse 2.6s ease-in-out ${item.delay} infinite` }} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mx-auto w-full max-w-[420px] lg:mx-0">
            <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-6 shadow-[0_8px_32px_rgba(15,23,42,0.08)] backdrop-blur sm:p-8">
              <div className="mb-7">
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-teal-50 to-teal-100/60 text-xl text-teal-700">
                  <CloudServerOutlined />
                </div>
                <Typography.Title level={2} className="!mb-1.5 !text-2xl !font-semibold !tracking-tight !text-slate-900">
                  登录工作台
                </Typography.Title>
                <Typography.Text className="!text-[13px] !text-slate-500">
                  请输入账号密码访问系统
                </Typography.Text>
              </div>

              <Form<LoginForm> layout="vertical" onFinish={onSubmit} autoComplete="off" requiredMark={false}>
                <Form.Item
                  label={<span className="text-[13px] font-medium text-slate-700">账号</span>}
                  name="username"
                  rules={[{ required: true, message: '请输入账号' }]}
                  className="!mb-4"
                >
                  <Input
                    prefix={<UserOutlined className="mr-1.5 text-slate-400" />}
                    placeholder="请输入用户名或手机号"
                    size="large"
                    className="!h-11 !rounded-lg"
                  />
                </Form.Item>
                <Form.Item
                  label={<span className="text-[13px] font-medium text-slate-700">密码</span>}
                  name="password"
                  rules={[{ required: true, message: '请输入密码' }]}
                  className="!mb-6"
                >
                  <Input.Password
                    prefix={<LockOutlined className="mr-1.5 text-slate-400" />}
                    placeholder="请输入登录密码"
                    size="large"
                    className="!h-11 !rounded-lg"
                  />
                </Form.Item>

                <Form.Item className="!mb-4">
                  <Button
                    type="primary"
                    htmlType="submit"
                    size="large"
                    block
                    loading={submitting}
                    className="!h-12 !rounded-lg !text-[15px] !font-semibold"
                  >
                    登录工作台
                  </Button>
                </Form.Item>

                <div className="rounded-lg border border-slate-200/80 bg-slate-50/60 px-4 py-2.5 text-center">
                  <Typography.Text className="!text-[13px] !text-slate-500">
                    没有账号？
                    <Button
                      type="link"
                      className="!h-auto !p-0 !pl-1 !font-medium !text-teal-700 hover:!text-teal-800"
                      onClick={() => setApplyVisible(true)}
                    >
                      立即申请账号
                    </Button>
                  </Typography.Text>
                </div>
              </Form>
            </div>
          </div>
        </section>

        <footer className="mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-3 border-t border-slate-200/60 py-5 text-[13px] text-slate-500 sm:flex-row">
          <span>© {new Date().getFullYear()} {APP_TITLE}</span>
        </footer>
      </main>

      <Modal
        title={<span className="text-[16px] font-semibold text-slate-900">账号入驻申请</span>}
        open={applyVisible}
        confirmLoading={applySubmitting}
        onCancel={() => setApplyVisible(false)}
        onOk={handleApplySubmit}
        okText="提交申请"
        cancelText="取消"
        centered
        width={520}
        styles={{
          mask: { backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.40)' },
        }}
      >
        <div className="mb-4 mt-2 rounded-lg border border-teal-100 bg-teal-50/60 p-3 text-[13px] text-teal-800">
          <DatabaseOutlined className="mr-2" />
          提交后管理员会在后台审核，审核通过后即可登录平台。
        </div>
        <Form<ApplyAccountForm> form={applyForm} layout="vertical" requiredMark={false}>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">登录用户名</span>}
            name="username"
            rules={[
              { required: true, message: '请输入登录用户名' },
              { pattern: /^[A-Za-z0-9_.-]{3,30}$/, message: '用户名需为 3-30 位字母、数字、下划线、点或短横线' },
            ]}
          >
            <Input placeholder="审核通过后用于登录" />
          </Form.Item>
          <Form.Item label={<span className="text-[13px] font-medium text-slate-700">申请人姓名</span>} name="applicantName" rules={[{ required: true, message: '请输入申请人姓名' }]}>
            <Input placeholder="输入真实姓名" />
          </Form.Item>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">手机号</span>}
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '请输入有效手机号' },
            ]}
          >
            <Input placeholder="常用联系方式" />
          </Form.Item>
          <Form.Item label={<span className="text-[13px] font-medium text-slate-700">企业邮箱</span>} name="email" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="用于接收通知（选填）" />
          </Form.Item>
          <Form.Item label={<span className="text-[13px] font-medium text-slate-700">申请说明</span>} name="reason" rules={[{ required: true, message: '请填写申请原因' }]}>
            <Input.TextArea rows={4} maxLength={200} showCount placeholder="请简述您的业务背景和使用目的" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
