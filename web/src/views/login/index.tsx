import {
  DatabaseOutlined,
} from '@ant-design/icons';
import { Form, Input, Modal, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { applyAccountRequest, loginRequest } from '../../api/modules/auth';
import { useAuthStore } from '../../store/auth';

type LoginForm = {
  username: string;
  password: string;
};

type ApplyAccountForm = {
  username: string;
  applicantName: string;
  enterpriseName: string;
  phone: string;
  password: string;
  confirmPassword: string;
  reason: string;
};

// Inline SVG Icon components matching Lucide icons exactly
const UserIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const LockIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

const EyeIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
    <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
    <path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
    <line x1="2" x2="22" y1="2" y2="22" />
  </svg>
);

const ArrowRightIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </svg>
);

const CpuIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <rect width="16" height="16" x="4" y="4" rx="2" />
    <rect width="6" height="6" x="9" y="9" rx="1" />
    <path d="M9 1v3" />
    <path d="M15 1v3" />
    <path d="M9 20v3" />
    <path d="M15 20v3" />
    <path d="M20 9h3" />
    <path d="M20 15h3" />
    <path d="M1 9h3" />
    <path d="M1 15h3" />
  </svg>
);

const SparklesIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
  </svg>
);

const GlobeIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
    <path d="M2 12h20" />
  </svg>
);

const FingerprintIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
    <path d="M12 10a2 2 0 0 0-2 2v3" />
    <path d="M14 10a4 4 0 0 0-8 0v4" />
    <path d="M8 14a6 6 0 0 0 8-3v-1" />
    <path d="M18 10a8 8 0 0 0-16 0v5" />
    <path d="M12 2a10 10 0 0 0-10 10v6" />
    <path d="M22 12a10 10 0 0 0-10-10" />
    <path d="M22 12v6" />
    <path d="M12 22a10 10 0 0 0 10-10" />
  </svg>
);

export const LoginPage = () => {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const [applyVisible, setApplyVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applyForm] = Form.useForm<ApplyAccountForm>();

  const [formData, setFormData] = useState({ username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);

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
        tenant: response.user.tenant,
        isSuperuser: response.user.is_superuser,
        mustChangePassword: response.user.must_change_password,
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

  const handleNativeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void onSubmit(formData);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center relative overflow-hidden font-sans w-full">
      <style>
        {`
          @keyframes blob {
            0% { transform: translate(0px, 0px) scale(1); }
            33% { transform: translate(30px, -50px) scale(1.1); }
            66% { transform: translate(-20px, 20px) scale(0.9); }
            100% { transform: translate(0px, 0px) scale(1); }
          }
          .animate-blob {
            animation: blob 7s infinite;
          }
          .animation-delay-2000 {
            animation-delay: 2s;
          }
          .animation-delay-4000 {
            animation-delay: 4s;
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          @keyframes spin-reverse {
            to { transform: rotate(-360deg); }
          }
        `}
      </style>
      
      {/* 背景动态渐变和网格 */}
      <div className="absolute inset-0 z-0 opacity-40 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-teal-300 blur-[120px] mix-blend-multiply animate-blob" />
        <div className="absolute top-[20%] right-[-10%] w-[35%] h-[35%] rounded-full bg-blue-300 blur-[120px] mix-blend-multiply animate-blob animation-delay-2000" />
        <div className="absolute bottom-[-20%] left-[20%] w-[40%] h-[40%] rounded-full bg-indigo-300 blur-[120px] mix-blend-multiply animate-blob animation-delay-4000" />
      </div>
      
      {/* 细微的背景网格 */}
      <div 
        className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none" 
        style={{ backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)', backgroundSize: '40px 40px' }}
      />

      {/* 主体卡片容器 */}
      <div className="w-full max-w-6xl mx-auto p-4 relative z-10">
        <div className="bg-white/70 backdrop-blur-2xl rounded-3xl shadow-[0_8px_40px_-12px_rgba(0,0,0,0.1)] border border-white/50 overflow-hidden flex flex-col md:flex-row min-h-[600px]">
          
          {/* 左侧：品牌与视觉区 (深色科技风) */}
          <div className="w-full md:w-1/2 bg-slate-900 relative overflow-hidden flex flex-col justify-between p-12 text-white">
            {/* 左侧内部光效 */}
            <div className="absolute inset-0 z-0 opacity-30">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-teal-500 rounded-full blur-[100px]" />
            </div>

            {/* 顶部 Logo & 标题 */}
            <div className="relative z-10">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-teal-500/30">
                  <FingerprintIcon className="w-6 h-6 text-white" />
                </div>
                <h1 className="text-2xl font-bold tracking-wide">AI System</h1>
              </div>
              <h2 className="text-4xl font-semibold leading-tight mb-4">
                数字人管理平台
              </h2>
              <p className="text-slate-400 text-lg max-w-md leading-relaxed">
                创建、管理并驱动您的下一代虚拟数字分身。结合强大的 AI 模型，赋予数字人真实的灵魂与交互能力。
              </p>
            </div>

            {/* 抽象的科技动画节点 (替代原图的中间部分) */}
            <div className="relative z-10 flex-1 flex items-center justify-center py-12">
              <div className="relative w-64 h-64">
                {/* 核心光圈 */}
                <div className="absolute inset-0 border border-teal-500/30 rounded-full animate-[spin_10s_linear_infinite]" />
                <div className="absolute inset-4 border border-blue-500/20 rounded-full animate-[spin_15s_linear_infinite_reverse]" />
                <div className="absolute inset-8 border border-indigo-500/20 rounded-full animate-[spin_8s_linear_infinite]" />
                
                {/* 核心立方/图标 */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 bg-slate-800 rounded-2xl border border-teal-500/50 shadow-[0_0_30px_rgba(20,184,166,0.3)] flex items-center justify-center">
                  <CpuIcon className="w-10 h-10 text-teal-400" />
                </div>

                {/* 浮动标签 */}
                <div className="absolute top-4 -left-12 bg-white/10 backdrop-blur-md border border-white/10 px-4 py-2 rounded-full flex items-center space-x-2 animate-bounce" style={{ animationDuration: '3s' }}>
                  <SparklesIcon className="w-4 h-4 text-amber-300" />
                  <span className="text-sm font-medium text-slate-200">AI 驱动引擎</span>
                </div>
                <div className="absolute bottom-10 -right-8 bg-white/10 backdrop-blur-md border border-white/10 px-4 py-2 rounded-full flex items-center space-x-2 animate-bounce" style={{ animationDuration: '4s', animationDelay: '1s' }}>
                  <GlobeIcon className="w-4 h-4 text-blue-300" />
                  <span className="text-sm font-medium text-slate-200">全终端渲染</span>
                </div>
              </div>
            </div>

            {/* 底部版权声明 */}
            <div className="relative z-10 text-slate-500 text-sm">
              &copy; 2026 版权所有. All rights reserved.
            </div>
          </div>

          {/* 右侧：登录表单区 (高亮、清晰) */}
          <div className="w-full md:w-1/2 p-8 md:p-16 flex flex-col justify-center bg-white/40">
            <div className="max-w-md w-full mx-auto">
              
              <div className="mb-10 text-center md:text-left">
                <h3 className="text-3xl font-bold text-slate-800 mb-2">登录工作台</h3>
                <p className="text-slate-500">欢迎回来，请输入您的账号进行身份验证</p>
              </div>

              <form onSubmit={handleNativeSubmit} className="space-y-6">
                
                {/* 用户名输入 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700 block">用户名</label>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <UserIcon className="h-5 w-5 text-slate-400 group-focus-within:text-teal-500 transition-colors" />
                    </div>
                    <input
                      type="text"
                      className="block w-full pl-11 pr-4 py-3.5 bg-white border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all shadow-sm"
                      placeholder="在此处输入用户名"
                      value={formData.username}
                      onChange={(e) => setFormData({...formData, username: e.target.value})}
                      required
                    />
                  </div>
                </div>

                {/* 密码输入 */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700 block">登录密码</label>
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <LockIcon className="h-5 w-5 text-slate-400 group-focus-within:text-teal-500 transition-colors" />
                    </div>
                    <input
                      type={showPassword ? "text" : "password"}
                      className="block w-full pl-11 pr-12 py-3.5 bg-white border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all shadow-sm"
                      placeholder="••••••••"
                      value={formData.password}
                      onChange={(e) => setFormData({...formData, password: e.target.value})}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600 transition-colors focus:outline-none"
                    >
                      {showPassword ? <EyeOffIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                    </button>
                  </div>
                </div>

                {/* 登录按钮 */}
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full flex items-center justify-center py-3.5 px-4 border border-transparent rounded-xl shadow-lg shadow-teal-500/30 text-base font-medium text-white bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-600 hover:to-emerald-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-all transform active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  ) : (
                    <>
                      <span>进入工作台</span>
                      <ArrowRightIcon className="ml-2 h-5 w-5" />
                    </>
                  )}
                </button>
                
              </form>

              {/* 底部申请链接 */}
              <div className="mt-8 pt-8 border-t border-slate-200 text-center md:text-left">
                <p className="text-center text-sm text-slate-500">
                  没有账号？{' '}
                  <button
                    type="button"
                    onClick={() => setApplyVisible(true)}
                    className="font-medium text-teal-600 hover:text-teal-500 transition-colors"
                  >
                    立即申请账号
                  </button>
                </p>
              </div>

            </div>
          </div>

        </div>
      </div>

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
              { pattern: /^[A-Za-z0-9]{3,30}$/, message: '用户名需为 3-30 位英文字母或数字' },
            ]}
          >
            <Input placeholder="审核通过后用于登录（字母或数字，至少 3 位，需全局唯一）" />
          </Form.Item>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">申请人姓名</span>}
            name="applicantName"
            rules={[{ required: true, message: '请输入申请人姓名' }]}
          >
            <Input placeholder="输入真实姓名" />
          </Form.Item>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">企业名称</span>}
            name="enterpriseName"
            rules={[{ required: true, message: '请输入企业名称' }]}
          >
            <Input placeholder="所属公司或组织全称" maxLength={128} />
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
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">密码</span>}
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码长度不少于 6 位' },
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  if (/^\d+$/.test(value)) {
                    return Promise.reject(new Error('密码不能为纯数字'));
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <Input.Password placeholder="不少于 6 位，且不能为纯数字" maxLength={128} />
          </Form.Item>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">确认密码</span>}
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请再次输入密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入密码" maxLength={128} />
          </Form.Item>
          <Form.Item
            label={<span className="text-[13px] font-medium text-slate-700">申请说明</span>}
            name="reason"
            rules={[{ required: true, message: '请填写申请原因' }]}
          >
            <Input.TextArea rows={4} maxLength={200} showCount placeholder="请简述您的业务背景 and 使用目的" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
