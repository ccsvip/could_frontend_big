import { IconLock } from '@tabler/icons-react';
import { Button, Form, Input, Typography, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePasswordRequest } from '../../api/modules/auth';
import { useAuthStore } from '../../store/auth';

type ForceChangeForm = {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
};

/**
 * 员工首次登录 / 被重置密码后的强制改密页。
 * 由 AuthGuard 在 mustChangePassword=true 时全屏渲染，挡住所有业务页面。
 * 改密成功后后端清除 must_change_password 标志；前端登出重登即解除拦截。
 */
export const ForcePasswordChangePage = () => {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const username = useAuthStore((state) => state.username);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<ForceChangeForm>();

  const onSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await changePasswordRequest({ oldPassword: values.oldPassword, newPassword: values.newPassword });
      message.success('密码修改成功，请用新密码重新登录');
      logout();
      navigate('/login', { replace: true });
    } catch {
      // 校验 / 拦截器已处理
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200/80 bg-white p-8 shadow-[0_8px_32px_rgba(15,23,42,0.08)]">
        <div className="mb-6">
          <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-xl text-amber-600">
            <IconLock />
          </div>
          <Typography.Title level={3} className="!mb-1.5">
            请先修改初始密码
          </Typography.Title>
          <Typography.Text className="!text-[13px] !text-slate-500">
            {username ? `${username}，` : ''}为保障账号安全，首次登录需修改管理员设置的初始密码。
          </Typography.Text>
        </div>

        <Form<ForceChangeForm> form={form} layout="vertical" requiredMark={false}>
          <Form.Item
            name="oldPassword"
            label="当前密码"
            rules={[{ required: true, message: '请输入当前（初始）密码' }]}
          >
            <Input.Password placeholder="管理员告知的初始密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="newPassword"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '新密码至少 8 位' },
            ]}
          >
            <Input.Password placeholder="设置你自己的新密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="确认新密码"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的新密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" block size="large" loading={submitting} onClick={onSubmit} className="!h-11">
            修改并重新登录
          </Button>
        </Form>
      </div>
    </div>
  );
};
