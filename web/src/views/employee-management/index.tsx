import { PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Checkbox,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tree,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { DataNode } from 'antd/es/tree';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  createEmployee,
  createTenantRole,
  deleteTenantRole,
  fetchEmployees,
  fetchMyTenantCatalog,
  fetchTenantRoles,
  resetEmployeePassword,
  updateEmployee,
  updateTenantRole,
  type EmployeeRecord,
  type TenantRoleRecord,
} from '../../api/modules/employees';
import type { MenuCatalogResponse } from '../../api/modules/tenants';

const normalizeMenuKeyToModule = (key: string): string =>
  key.replace(/^\//, '').replace(/[/-]/g, '_');

const buildMenuTree = (menus: MenuCatalogResponse['menus']): DataNode[] => {
  const byId = new Map(menus.map((m) => [m.id, m]));
  const childrenOf = (parentId: number | null): DataNode[] =>
    menus
      .filter((m) => (m.parent ?? null) === parentId || (parentId === null && m.parent != null && !byId.has(m.parent)))
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((m) => {
        const children = childrenOf(m.id);
        return { key: m.id, title: m.name, children: children.length ? children : undefined };
      });
  return childrenOf(null);
};

const EmployeesTab = ({ roles }: { roles: TenantRoleRecord[] }) => {
  const [employees, setEmployees] = useState<EmployeeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [resetTarget, setResetTarget] = useState<EmployeeRecord | null>(null);
  const [form] = Form.useForm();
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

  const handleChangeRole = async (record: EmployeeRecord, roleId: number | null) => {
    await updateEmployee(record.id, { roleId });
    message.success('角色已更新');
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

  const roleOptions = roles.map((r) => ({ label: r.name, value: r.id }));

  const columns: ColumnsType<EmployeeRecord> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '姓名', dataIndex: 'displayName', key: 'displayName' },
    {
      title: '角色',
      key: 'role',
      render: (_, record) => (
        <Select
          size="small"
          style={{ minWidth: 120 }}
          placeholder="未分配"
          allowClear
          value={record.roleId ?? undefined}
          options={roleOptions}
          onChange={(val) => handleChangeRole(record, val ?? null)}
        />
      ),
    },
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
      width: 220,
      render: (_, record) => (
        <Space>
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
          <Form.Item name="roleId" label="分配角色">
            <Select allowClear placeholder="可稍后分配" options={roleOptions} />
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

const RolesTab = ({ onRolesChanged }: { onRolesChanged: () => void }) => {
  const [roles, setRoles] = useState<TenantRoleRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState<MenuCatalogResponse | null>(null);
  const [editing, setEditing] = useState<TenantRoleRecord | 'new' | null>(null);
  const [form] = Form.useForm();
  const [checkedMenuIds, setCheckedMenuIds] = useState<number[]>([]);
  const [checkedPermIds, setCheckedPermIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const loadedRef = useRef(false);

  const load = async () => {
    setLoading(true);
    try {
      const [rolesData, cat] = await Promise.all([fetchTenantRoles(), fetchMyTenantCatalog()]);
      setRoles(rolesData.results);
      setCatalog(cat);
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

  const openEditor = (role: TenantRoleRecord | 'new') => {
    setEditing(role);
    if (role === 'new') {
      form.resetFields();
      setCheckedMenuIds([]);
      const defaultPermIds = catalog
        ? catalog.permissionPoints.filter((p) => p.module !== 'employees').map((p) => p.id)
        : [];
      setCheckedPermIds(defaultPermIds);
    } else {
      form.setFieldsValue({ name: role.name, code: role.code, description: role.description });
      setCheckedMenuIds(role.menuIds);
      setCheckedPermIds(role.permissionPointIds);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = { ...values, menuIds: checkedMenuIds, permissionPointIds: checkedPermIds };
      if (editing === 'new') {
        await createTenantRole(payload);
        message.success('角色创建成功');
      } else if (editing) {
        await updateTenantRole(editing.id, payload);
        message.success('角色已更新');
      }
      setEditing(null);
      void load();
      onRolesChanged();
    } catch {
      // 校验/拦截器已处理
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (role: TenantRoleRecord) => {
    await deleteTenantRole(role.id);
    message.success('角色已删除');
    void load();
    onRolesChanged();
  };

  const menuTree = useMemo(() => (catalog ? buildMenuTree(catalog.menus) : []), [catalog]);
  const permsByModule = useMemo(() => {
    const groups = new Map<string, MenuCatalogResponse['permissionPoints']>();
    catalog?.permissionPoints.forEach((p) => {
      const list = groups.get(p.module) ?? [];
      list.push(p);
      groups.set(p.module, list);
    });
    return Array.from(groups.entries());
  }, [catalog]);
  const menuPermIdMap = useMemo(() => {
    const map = new Map<number, number[]>();
    if (!catalog) return map;
    const idsByModule = new Map<string, number[]>();
    catalog.permissionPoints.forEach((p) => {
      const list = idsByModule.get(p.module) ?? [];
      list.push(p.id);
      idsByModule.set(p.module, list);
    });
    catalog.menus.forEach((m) => {
      const ids = idsByModule.get(normalizeMenuKeyToModule(m.key));
      if (ids?.length) map.set(m.id, ids);
    });
    return map;
  }, [catalog]);

  const columns: ColumnsType<TenantRoleRecord> = [
    { title: '角色名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code', render: (c: string) => <Tag>{c}</Tag> },
    { title: '菜单数', key: 'menuCount', width: 90, render: (_, r) => r.menuIds.length },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" onClick={() => openEditor(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除该角色？" onConfirm={() => handleDelete(record)}>
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
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor('new')}>
          新建角色
        </Button>
      </div>
      <Table rowKey="id" columns={columns} dataSource={roles} loading={loading} />

      <Drawer
        title={editing === 'new' ? '新建角色' : '编辑角色'}
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        width={520}
        extra={
          <Button type="primary" loading={saving} onClick={handleSave}>
            保存
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="角色名称" rules={[{ required: true, message: '请输入角色名称' }]}>
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item
            name="code"
            label="角色编码"
            rules={[{ required: true, message: '请输入角色编码' }]}
            extra="公司内唯一的英文标识"
          >
            <Input maxLength={64} disabled={editing !== 'new'} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} maxLength={200} />
          </Form.Item>
        </Form>

        <Typography.Title level={5}>可见菜单</Typography.Title>
        <Tree
          checkable
          selectable={false}
          treeData={menuTree}
          checkedKeys={checkedMenuIds}
          onCheck={(checked) => {
            const keys = Array.isArray(checked) ? checked : checked.checked;
            const nextMenuIds = keys.map(Number);
            const prevSet = new Set(checkedMenuIds);
            const nextSet = new Set(nextMenuIds);
            const added = nextMenuIds.filter((id) => !prevSet.has(id));
            const removed = checkedMenuIds.filter((id) => !nextSet.has(id));

            setCheckedMenuIds(nextMenuIds);
            if (!added.length && !removed.length) return;

            setCheckedPermIds((prev) => {
              const result = new Set(prev);
              added.forEach((id) => menuPermIdMap.get(id)?.forEach((pid) => result.add(pid)));
              const stillNeeded = new Set<number>();
              nextMenuIds.forEach((id) => menuPermIdMap.get(id)?.forEach((pid) => stillNeeded.add(pid)));
              removed.forEach((id) =>
                menuPermIdMap.get(id)?.forEach((pid) => {
                  if (!stillNeeded.has(pid)) result.delete(pid);
                }),
              );
              return Array.from(result);
            });
          }}
        />

        <Typography.Title level={5} className="!mt-6">
          权限点
        </Typography.Title>
        {permsByModule.map(([module, points]) => (
          <div key={module} className="mb-3">
            <div className="mb-1 text-[13px] font-medium text-slate-500">{module}</div>
            <Checkbox.Group
              value={checkedPermIds}
              onChange={(vals) => {
                const ids = vals as number[];
                const otherIds = checkedPermIds.filter((id) => !points.some((p) => p.id === id));
                setCheckedPermIds([...otherIds, ...ids]);
              }}
              options={points.map((p) => ({ label: p.name, value: p.id }))}
            />
          </div>
        ))}
      </Drawer>
    </div>
  );
};

export const EmployeeManagementPage = () => {
  // 角色变更后让员工 Tab 的角色下拉刷新：用 key 强制重挂员工 Tab。
  const [rolesVersion, setRolesVersion] = useState(0);
  const [roles, setRoles] = useState<TenantRoleRecord[]>([]);

  useEffect(() => {
    void fetchTenantRoles().then((data) => setRoles(data.results)).catch(() => undefined);
  }, [rolesVersion]);

  return (
    <div>
      <Typography.Title level={4}>员工管理</Typography.Title>
      <Tabs
        items={[
          {
            key: 'employees',
            label: '员工',
            children: <EmployeesTab key={rolesVersion} roles={roles} />,
          },
          {
            key: 'roles',
            label: '角色',
            children: <RolesTab onRolesChanged={() => setRolesVersion((v) => v + 1)} />,
          },
        ]}
      />
    </div>
  );
};
