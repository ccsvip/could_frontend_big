import { PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useRef, useState } from 'react';
import {
  createEmployee,
  deleteEmployee,
  fetchEmployees,
  resetEmployeePassword,
  updateEmployee,
  type EmployeeRecord,
} from '../../api/modules/employees';

const EmployeesTab = () => {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [editTarget, setEditTarget] = useState<EmployeeRecord | null>(null);
  const [resetTarget, setResetTarget] = useState<EmployeeRecord | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [resetForm] = Form.useForm();
  const loadedRef = useRef(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchEmployees();
      setEmployees(data.results);
    } catch {
      // 拦截器已提示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    void load();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createEmployee(values);
      message.success('员工创建成功，初始密码已设置，员工首次登录需改密');
      setCreateVisible(false);
      form.resetFields();
      void load();
    } catch {
      // 校验/拦截器已处理
    }
  };

  const handleToggleActive = async (record: EmployeeRecord) => {
    await updateEmployee(record.id, { isActive: !record.isActive });
    message.success(record.isActive ? '员工已停用' : '员工已启用');
    void load();
  };

  const openEdit = (record: EmployeeRecord) => {
    setEditTarget(record);
    editForm.setFieldsValue({
      username: record.username,
      displayName: record.displayName,
      roleName: record.roleName,
    });
  };

  const handleEdit = async () => {
    if (!editTarget) return;
    try {
      const values = await editForm.validateFields();
      await updateEmployee(editTarget.id, values);
      message.success('员工信息已更新');
      setEditTarget(null);
      editForm.resetFields();
      void load();
    } catch {
      // 校验/拦截器已处理
    }
  };

  const handleDelete = async (record: EmployeeRecord) => {
    await deleteEmployee(record.id);
    message.success('员工已删除');
    void load();
  };

  const handleReset = async () => {
    if (!resetTarget) return;
    try {
      const values = await resetForm.validateFields();
      await resetEmployeePassword(resetTarget.id, values.newPassword);
      message.success('密码已重置，员工下次登录需改密');
      setResetTarget(null);
      resetForm.resetFields();
    } catch {
      // 校验/拦截器已处理
    }
  };

  const columns: ColumnsType<EmployeeRecord> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '姓名', dataIndex: 'displayName', key: 'displayName' },
    { title: '角色名称', dataIndex: 'roleName', key: 'roleName' },
    {
      title: '状态',
      key: 'status',
      width: 140,
      render: (_, record) => (
        <Space size={4}>
          <Tag color={record.isActive ? 'success' : 'default'}>{record.isActive ? '启用' : '停用'}</Tag>
          {record.mustChangePassword ? <Tag color="warning">待改密</Tag> : null}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button type="link" size="small" onClick={() => setResetTarget(record)}>
            重置密码
          </Button>
          <Popconfirm
            title={record.isActive ? '确认停用该员工？' : '确认启用该员工？'}
            onConfirm={() => handleToggleActive(record)}
          >
            <Button type="link" size="small" danger={record.isActive}>
              {record.isActive ? '停用' : '启用'}
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确认删除该员工？"
            description="删除后该员工账号将无法登录。"
            onConfirm={() => handleDelete(record)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
          新建员工
        </Button>
      </div>
      <Table rowKey="id" columns={columns} dataSource={employees} loading={loading} />

      <Modal
        title="新建员工"
        open={createVisible}
        onOk={handleCreate}
        onCancel={() => setCreateVisible(false)}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false} className="pt-2">
          <Form.Item
            name="username"
            label="登录用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { pattern: /^[A-Za-z0-9]{3,30}$/, message: '用户名需为 3-30 位英文字母或数字' },
            ]}
          >
            <Input placeholder="字母或数字，全局唯一" />
          </Form.Item>
          <Form.Item name="displayName" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="员工真实姓名" maxLength={64} />
          </Form.Item>
          <Form.Item
            name="password"
            label="初始密码"
            rules={[
              { required: true, message: '请输入初始密码' },
              { min: 6, message: '密码长度不少于 6 位' },
            ]}
          >
            <Input.Password placeholder="员工首次登录将被要求修改" maxLength={128} />
          </Form.Item>
          <Form.Item name="roleName" label="角色名称" rules={[{ required: true, message: '请输入角色名称' }]}>
            <Input placeholder="可重复，不可为空" maxLength={64} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editTarget ? `编辑员工 · ${editTarget.displayName}` : '编辑员工'}
        open={Boolean(editTarget)}
        onOk={handleEdit}
        onCancel={() => {
          setEditTarget(null);
          editForm.resetFields();
        }}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical" preserve={false} className="pt-2">
          <Form.Item
            name="username"
            label="登录用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { pattern: /^[A-Za-z0-9]{3,30}$/, message: '用户名需为 3-30 位英文字母或数字' },
            ]}
          >
            <Input placeholder="字母或数字，全局唯一" />
          </Form.Item>
          <Form.Item name="displayName" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="员工真实姓名" maxLength={64} />
          </Form.Item>
          <Form.Item name="roleName" label="角色名称" rules={[{ required: true, message: '请输入角色名称' }]}>
            <Input placeholder="可重复，不可为空" maxLength={64} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={resetTarget ? `重置密码 · ${resetTarget.displayName}` : '重置密码'}
        open={Boolean(resetTarget)}
        onOk={handleReset}
        onCancel={() => setResetTarget(null)}
        okText="重置"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={resetForm} layout="vertical" preserve={false} className="pt-2">
          <Form.Item
            name="newPassword"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码长度不少于 6 位' },
            ]}
          >
            <Input.Password placeholder="员工下次登录需再次修改" maxLength={128} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export const EmployeeManagementPage = () => {
  return (
    <div>
      <Typography.Title level={4}>员工管理</Typography.Title>
      <EmployeesTab />
    </div>
  );
};
