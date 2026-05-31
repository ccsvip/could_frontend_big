import { ApartmentOutlined, PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Checkbox,
  Drawer,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Tree,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { DataNode } from 'antd/es/tree';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  assignTenantMenus,
  createTenant,
  fetchMenuCatalog,
  fetchTenantMenuSelection,
  fetchTenants,
  type MenuCatalogResponse,
  type TenantRecord,
} from '../../api/modules/tenants';

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

export const TenantManagementPage = () => {
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [form] = Form.useForm<{ name: string }>();
  const hasLoadedRef = useRef(false);

  const [catalog, setCatalog] = useState<MenuCatalogResponse | null>(null);
  const [assignTenant, setAssignTenant] = useState<TenantRecord | null>(null);
  const [checkedMenuIds, setCheckedMenuIds] = useState<number[]>([]);
  const [checkedPermIds, setCheckedPermIds] = useState<number[]>([]);
  const [assignSaving, setAssignSaving] = useState(false);

  const loadTenants = async () => {
    setLoading(true);
    try {
      const data = await fetchTenants();
      setTenants(data.results);
    } catch {
      // 拦截器已提示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;
    void loadTenants();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createTenant(values);
      message.success('公司创建成功');
      setCreateVisible(false);
      form.resetFields();
      void loadTenants();
    } catch {
      // 校验或拦截器已处理
    }
  };

  const openAssign = async (tenant: TenantRecord) => {
    setAssignTenant(tenant);
    try {
      const [cat, selection] = await Promise.all([
        catalog ? Promise.resolve(catalog) : fetchMenuCatalog(),
        fetchTenantMenuSelection(tenant.id),
      ]);
      setCatalog(cat);
      setCheckedMenuIds(selection.menuIds);
      setCheckedPermIds(selection.permissionPointIds);
    } catch {
      setAssignTenant(null);
    }
  };

  const handleAssignSave = async () => {
    if (!assignTenant) return;
    setAssignSaving(true);
    try {
      await assignTenantMenus(assignTenant.id, {
        menuIds: checkedMenuIds,
        permissionPointIds: checkedPermIds,
      });
      message.success('菜单分配已保存');
      setAssignTenant(null);
      void loadTenants();
    } catch {
      // 拦截器已提示
    } finally {
      setAssignSaving(false);
    }
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

  const columns: ColumnsType<TenantRecord> = [
    { title: '公司名称', dataIndex: 'name', key: 'name' },
    { title: '标识', dataIndex: 'code', key: 'code', render: (code: string) => <Tag>{code}</Tag> },
    { title: '菜单数', dataIndex: 'menuCount', key: 'menuCount', width: 90 },
    { title: '成员数', dataIndex: 'memberCount', key: 'memberCount', width: 90 },
    {
      title: '状态',
      key: 'status',
      width: 120,
      render: (_, record) => (
        <Space size={4}>
          <Tag color={record.isActive ? 'success' : 'default'}>{record.isActive ? '启用' : '停用'}</Tag>
          {record.isLegacy ? <Tag color="warning">默认公司</Tag> : null}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_, record) => (
        <Button type="link" icon={<ApartmentOutlined />} onClick={() => openAssign(record)}>
          分配菜单
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">
          租户管理
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>
          新建公司
        </Button>
      </div>

      <Table rowKey="id" columns={columns} dataSource={tenants} loading={loading} />

      <Modal
        title="新建公司"
        open={createVisible}
        onOk={handleCreate}
        onCancel={() => setCreateVisible(false)}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false} className="pt-2">
          <Form.Item name="name" label="公司名称" rules={[{ required: true, message: '请输入公司名称' }]}>
            <Input placeholder="公司全称" maxLength={128} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={assignTenant ? `分配菜单 · ${assignTenant.name}` : '分配菜单'}
        open={Boolean(assignTenant)}
        onClose={() => setAssignTenant(null)}
        width={520}
        extra={
          <Button type="primary" loading={assignSaving} onClick={handleAssignSave}>
            保存
          </Button>
        }
      >
        <Typography.Title level={5}>可见菜单</Typography.Title>
        <Typography.Paragraph type="secondary" className="!text-[13px]">
          勾选该公司可使用的业务菜单。公司管理员只能在此范围内给员工分配。
        </Typography.Paragraph>
        <Tree
          checkable
          selectable={false}
          treeData={menuTree}
          checkedKeys={checkedMenuIds}
          onCheck={(checked) => {
            const keys = Array.isArray(checked) ? checked : checked.checked;
            setCheckedMenuIds(keys.map(Number));
          }}
        />

        <Typography.Title level={5} className="!mt-6">
          可用权限点
        </Typography.Title>
        <Typography.Paragraph type="secondary" className="!text-[13px]">
          公司可使用的操作权限上限（员工实际权限再按其角色取交集）。
        </Typography.Paragraph>
        {permsByModule.map(([module, points]) => (
          <div key={module} className="mb-3">
            <div className="mb-1 text-[13px] font-medium text-slate-500">{module}</div>
            <Checkbox.Group
              value={checkedPermIds}
              onChange={(vals) => {
                const ids = vals as number[];
                // 合并其它模块已选项，避免本组 onChange 覆盖掉别组的选择
                const otherModuleIds = checkedPermIds.filter(
                  (id) => !points.some((p) => p.id === id),
                );
                setCheckedPermIds([...otherModuleIds, ...ids]);
              }}
              options={points.map((p) => ({ label: p.name, value: p.id }))}
            />
          </div>
        ))}
      </Drawer>
    </div>
  );
};
