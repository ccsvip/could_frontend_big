import {
  ApartmentOutlined,
  AudioOutlined,
  CheckCircleOutlined,
  CloudOutlined,
  CustomerServiceOutlined,
  DesktopOutlined,
  EnvironmentOutlined,
  ExportOutlined,
  FileImageOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  LockOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  PictureOutlined,
  NotificationOutlined,
  RobotOutlined,
  SolutionOutlined,
  SoundOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { Avatar, Button, Drawer, Dropdown, Form, Grid, Input, Layout, Menu, Modal, Typography, message } from 'antd';
import type { MenuProps } from 'antd';
import dayjs, { type Dayjs } from 'dayjs';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { changePasswordRequest, type ChangePasswordPayload } from '../api/modules/auth';
import { fetchTenants, type TenantRecord } from '../api/modules/tenants';
import { BrandMark } from '../components/brand-mark';
import { useAuthStore, type AppMenu } from '../store/auth';

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;
const APP_TITLE = import.meta.env.VITE_APP_TITLE || '数字人后台管理平台';
const SIDEBAR_WIDTH = 286;
const SIDEBAR_COLLAPSED_WIDTH = 80;
const SIDEBAR_COLLAPSE_STORAGE_KEY = 'app:sidebar-collapsed';

const menuIconMap = {
  DesktopOutlined: <DesktopOutlined />,
  ApartmentOutlined: <ApartmentOutlined />,
  TeamOutlined: <TeamOutlined />,
  SolutionOutlined: <SolutionOutlined />,
  PictureOutlined: <PictureOutlined />,
  VideoCameraOutlined: <VideoCameraOutlined />,
  CustomerServiceOutlined: <CustomerServiceOutlined />,
  FileTextOutlined: <FileTextOutlined />,
  RobotOutlined: <RobotOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  CloudOutlined: <CloudOutlined />,
  AudioOutlined: <AudioOutlined />,
  SoundOutlined: <SoundOutlined />,
  MessageOutlined: <MessageOutlined />,
  FileImageOutlined: <FileImageOutlined />,
  FileSearchOutlined: <FileSearchOutlined />,
  NotificationOutlined: <NotificationOutlined />,
  EnvironmentOutlined: <EnvironmentOutlined />,
  ExportOutlined: <ExportOutlined />,
} as const;

const hiddenMenuPaths = new Set(['/commands/task-lists', 'commands/task-lists']);
const commandRootPaths = new Set(['/commands', 'commands']);

// 平台超管「按公司浏览」时，每家公司可下钻的业务模块。segment 对应 /tenants/:tenantId/<segment> 子路由，
// 图标与中文名复用 menuIconMap 风格，保持与后端 menus 渲染一致的观感。
type SuperAdminTenantModule = {
  segment: string;
  label: string;
  icon: keyof typeof menuIconMap;
  children?: ReadonlyArray<SuperAdminTenantModule>;
};

const SUPER_ADMIN_TENANT_MODULES: ReadonlyArray<SuperAdminTenantModule> = [
  { segment: 'devices', label: '设备管理', icon: 'DesktopOutlined' },
  {
    segment: 'resources',
    label: '资源管理',
    icon: 'PictureOutlined',
    children: [
      { segment: 'images', label: '背景图片管理', icon: 'PictureOutlined' },
      { segment: 'videos', label: '视频管理', icon: 'VideoCameraOutlined' },
      { segment: 'scrolling-texts', label: '滚动文本', icon: 'NotificationOutlined' },
      { segment: 'voice-tones', label: '音色管理', icon: 'CustomerServiceOutlined' },
      { segment: 'models', label: '模型管理', icon: 'RobotOutlined' },
    ],
  },
  { segment: 'knowledge-base', label: '知识库', icon: 'FileTextOutlined' },
  { segment: 'commands', label: '指令管理', icon: 'ThunderboltOutlined' },
  {
    segment: 'ai-models',
    label: 'AI大模型',
    icon: 'RobotOutlined',
    children: [
      { segment: 'asr', label: 'ASR管理', icon: 'AudioOutlined' },
      { segment: 'llm', label: 'LLM管理', icon: 'CloudOutlined' },
      { segment: 'tts', label: 'TTS管理', icon: 'SoundOutlined' },
      { segment: 'chat', label: '聊天室', icon: 'MessageOutlined' },
    ],
  },
];

const buildSuperAdminTenantModuleMenus = (
  tenantId: number,
  modules: ReadonlyArray<SuperAdminTenantModule>,
  parentSegment = '',
): AppMenu[] =>
  modules.map((module) => {
    const segmentPath = parentSegment ? `${parentSegment}/${module.segment}` : module.segment;
    const children = module.children
      ? buildSuperAdminTenantModuleMenus(tenantId, module.children, segmentPath)
      : undefined;

    return {
      key: `tenant-${tenantId}-${segmentPath}`,
      label: module.label,
      icon: module.icon,
      path: `/tenants/${tenantId}/${segmentPath}`,
      children: children && children.length > 0 ? children : undefined,
    };
  });

// 构建超管专属导航树：租户管理(可展开→各公司→各公司业务模块)、账号申请管理、日志管理。
// 与后端 menus 流程完全分流，仅在 hasPermission('tenant.management.view') 时启用。
const buildSuperAdminMenus = (tenants: TenantRecord[]): AppMenu[] => [
  {
    key: 'tenants',
    label: '租户管理',
    icon: 'ApartmentOutlined',
    path: '/tenants',
    children: tenants.map((tenant) => ({
      key: `tenant-${tenant.id}`,
      label: tenant.name,
      icon: 'TeamOutlined',
      children: buildSuperAdminTenantModuleMenus(tenant.id, SUPER_ADMIN_TENANT_MODULES),
    })),
  },
  {
    key: 'account-applications',
    label: '账号申请管理',
    icon: 'SolutionOutlined',
    path: '/account-applications',
  },
  {
    key: 'logs',
    label: '日志管理',
    icon: 'FileSearchOutlined',
    path: '/logs',
  },
];

const commandWorkspacePaths = new Set(['/commands/groups', 'commands/groups']);
const commandInlineWorkspacePaths = new Set(['/commands/control', 'commands/control', '/commands/tasks', 'commands/tasks']);

const filterVisibleMenus = (menus: AppMenu[]): AppMenu[] => {
  return menus
    .filter((menu) => !hiddenMenuPaths.has(menu.path || menu.key))
    .map((menu) => {
      const children = menu.children ? filterVisibleMenus(menu.children) : undefined;
      return {
        ...menu,
        children: children && children.length > 0 ? children : undefined,
      };
    });
};

const normalizeSidebarMenus = (menus: AppMenu[]): AppMenu[] => {
  return menus.map((menu) => {
    const menuPath = menu.path || menu.key;
    const children = menu.children ? normalizeSidebarMenus(menu.children) : undefined;

    if (commandRootPaths.has(menuPath)) {
      const workspaceMenu = children?.find((child) => commandWorkspacePaths.has(child.path || child.key));
      const sidebarChildren = children?.filter((child) => !commandInlineWorkspacePaths.has(child.path || child.key)) ?? [];
      const hasSidebarChildren = sidebarChildren.length > 0;
      // 控制/任务指令由统一工作台左侧分组承载，点位管理和导出管理仍作为侧边栏二级入口展示。
      return {
        ...menu,
        path: hasSidebarChildren ? menu.path || '/commands' : workspaceMenu?.path || menu.path || '/commands/groups',
        children: hasSidebarChildren ? sidebarChildren : undefined,
      };
    }

    return {
      ...menu,
      children,
    };
  });
};

const buildMenuItem = (
  menu: AppMenu,
  navigate: (path: string) => void,
): NonNullable<MenuProps['items']>[number] => {
  const children = menu.children?.map((child) => buildMenuItem(child, navigate)).filter(Boolean);
  const hasChildren = Boolean(children && children.length > 0);

  return {
    key: menu.key,
    icon: menu.icon ? menuIconMap[menu.icon as keyof typeof menuIconMap] : undefined,
    label: menu.label,
    children: hasChildren ? children : undefined,
    popupClassName: hasChildren ? 'app-sidebar-menu-popup' : undefined,
    onClick: hasChildren ? undefined : () => navigate(menu.path || menu.key),
  };
};

const findMenuTrail = (menus: AppMenu[], pathname: string, ancestors: AppMenu[] = []): AppMenu[] | null => {
  for (const menu of menus) {
    const trail = [...ancestors, menu];
    const isCommandRoot = commandRootPaths.has(menu.path || '') || commandRootPaths.has(menu.key);

    if (menu.path === pathname || menu.key === pathname) {
      return trail;
    }

    if (menu.children && menu.children.length > 0) {
      const childTrail = findMenuTrail(menu.children, pathname, trail);
      if (childTrail) {
        return childTrail;
      }
    }

    if (isCommandRoot && pathname.startsWith('/commands/')) {
      return trail;
    }
  }

  return null;
};

const useLiveNow = (): Dayjs => {
  const [now, setNow] = useState(() => dayjs());

  useEffect(() => {
    // 顶栏时间只承担状态感知，不参与业务逻辑。
    const timer = window.setInterval(() => setNow(dayjs()), 1000 * 30);
    return () => window.clearInterval(timer);
  }, []);

  return now;
};

type SidebarContentProps = {
  menuItems: MenuProps['items'];
  selectedMenuKey: string;
  openKeys: string[];
  onOpenChange: (keys: string[]) => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  showToggle?: boolean;
};

const SidebarContent = ({
  menuItems,
  selectedMenuKey,
  openKeys,
  onOpenChange,
  collapsed = false,
  onToggleCollapsed,
  showToggle = false,
}: SidebarContentProps) => (
  <div className="flex h-full flex-col bg-[#0f172a] text-white">
    <div className={`pb-3 pt-5 ${collapsed ? 'px-2' : 'px-5'}`}>
      {collapsed ? (
        <div className="flex justify-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-teal-500/30 to-teal-700/20 text-teal-200">
            <RobotOutlined className="text-lg" />
          </div>
        </div>
      ) : (
        <BrandMark title={APP_TITLE} subtitle="Operations Console" tone="dark" compact />
      )}
    </div>

    {!collapsed ? (
      <div className="px-4 pb-1">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.04] px-3 py-2.5">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-slate-100">服务运行中</div>
              <div className="truncate text-[11px] text-slate-500">权限与菜单已同步</div>
            </div>
            <CheckCircleOutlined className="text-emerald-400/80" />
          </div>
        </div>
      </div>
    ) : null}

    <div className={`custom-scrollbar mt-3 flex-1 overflow-y-auto pb-3 ${collapsed ? 'px-1' : 'px-2.5'}`}>
      <Menu
        mode="inline"
        selectedKeys={[selectedMenuKey]}
        {...(collapsed ? {} : { openKeys, onOpenChange: (keys: string[]) => onOpenChange(keys) })}
        items={menuItems}
        className="app-sidebar-menu !border-none !bg-transparent"
        theme="dark"
        inlineIndent={16}
        inlineCollapsed={collapsed}
        subMenuOpenDelay={0.1}
        subMenuCloseDelay={0.2}
      />
    </div>

    {showToggle && onToggleCollapsed ? (
      <div className={`shrink-0 border-t border-white/[0.06] ${collapsed ? 'px-2 py-3' : 'px-3 py-3'}`}>
        <button
          type="button"
          aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
          onClick={onToggleCollapsed}
          className={`flex h-10 w-full items-center gap-2.5 rounded-lg text-[13px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-white ${collapsed ? 'justify-center' : 'px-3'}`}
        >
          {collapsed ? <MenuUnfoldOutlined className="text-base" /> : <MenuFoldOutlined className="text-base" />}
          {!collapsed ? <span className="truncate">收起侧边栏</span> : null}
        </button>
      </div>
    ) : null}
  </div>
);

export const DashboardLayout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isDesktop = Boolean(screens.lg);
  const now = useLiveNow();
  const { username, role, logout, menus } = useAuthStore();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const isSuperAdmin = hasPermission('tenant.management.view');
  const [scopedTenants, setScopedTenants] = useState<TenantRecord[]>([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [passwordForm] = Form.useForm<ChangePasswordPayload & { confirmPassword: string }>();

  // 用户主动选择的折叠偏好（null = 跟随视口默认）。只有用户点击折叠按钮时才更新。
  const [userCollapsePreference, setUserCollapsePreference] = useState<boolean | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      const stored = window.localStorage.getItem(SIDEBAR_COLLAPSE_STORAGE_KEY);
      if (stored === '1') return true;
      if (stored === '0') return false;
      return null;
    } catch {
      return null;
    }
  });

  // 视口默认：lg ≤ width < xl 时默认折叠以缓解空间局促；xl 以上默认展开。
  // 在 antd useBreakpoint 完成首次解析前 (xl 仍为 undefined) 不返回折叠默认，避免首次渲染抖动。
  const breakpointsResolved = screens.xl !== undefined || screens.lg !== undefined || screens.md !== undefined;
  const viewportDefaultCollapsed = breakpointsResolved && isDesktop && !screens.xl;

  // 实际折叠状态：用户偏好优先，否则跟随视口默认。
  const sidebarCollapsed = isDesktop ? (userCollapsePreference ?? viewportDefaultCollapsed) : false;

  const handleToggleSidebar = useCallback(() => {
    setUserCollapsePreference((prev) => {
      const current = prev ?? viewportDefaultCollapsed;
      const next = !current;
      // 如果切换后等于当前视口默认值，则恢复"跟随视口默认"（清除偏好），让窗口缩放仍能联动。
      return next === viewportDefaultCollapsed ? null : next;
    });
  }, [viewportDefaultCollapsed]);

  // 持久化用户偏好（null 时移除条目，确保下次会话仍跟随视口默认）。
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      if (userCollapsePreference === null) {
        window.localStorage.removeItem(SIDEBAR_COLLAPSE_STORAGE_KEY);
      } else {
        window.localStorage.setItem(SIDEBAR_COLLAPSE_STORAGE_KEY, userCollapsePreference ? '1' : '0');
      }
    } catch {
      // ignore quota / privacy mode
    }
  }, [userCollapsePreference]);

  // 跟踪窗口宽度，让移动端 Drawer 宽度在 resize 时自适应。
  const [windowWidth, setWindowWidth] = useState(() =>
    typeof window === 'undefined' ? SIDEBAR_WIDTH : window.innerWidth,
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 平台超管拉取公司列表，构建「按公司浏览」二级菜单；非超管不发起该请求。
  useEffect(() => {
    if (!isSuperAdmin) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const data = await fetchTenants({ page_size: 100 });
        if (!cancelled) {
          setScopedTenants(data.results);
        }
      } catch {
        // 错误已由响应拦截器统一提示，这里只保证不抛出。
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSuperAdmin]);

  // 超管走「按公司浏览」自建导航树，与后端 menus 流程彻底分流；其余用户保持原有 menus 渲染。
  // 前端下线任务列表二级菜单，避免后端历史菜单配置继续渲染该入口。
  const visibleMenus = useMemo(
    () =>
      isSuperAdmin
        ? buildSuperAdminMenus(scopedTenants)
        : normalizeSidebarMenus(filterVisibleMenus(menus)),
    [isSuperAdmin, scopedTenants, menus],
  );
  const navigateFromMenu = useCallback(
    (path: string) => {
      navigate(path);
      setMobileMenuOpen(false);
    },
    [navigate],
  );
  const menuItems = useMemo<MenuProps['items']>(
    () => visibleMenus.map((menu) => buildMenuItem(menu, navigateFromMenu)),
    [navigateFromMenu, visibleMenus],
  );
  const activeMenuTrail = useMemo(() => findMenuTrail(visibleMenus, location.pathname) ?? [], [location.pathname, visibleMenus]);
  const activeOpenKeys = useMemo(() => activeMenuTrail.slice(0, -1).map((menu) => menu.key), [activeMenuTrail]);
  const [manualOpenKeys, setManualOpenKeys] = useState<string[]>([]);
  const openKeys = useMemo(
    () => Array.from(new Set([...manualOpenKeys, ...activeOpenKeys])),
    [activeOpenKeys, manualOpenKeys],
  );
  const currentMenuLabel = activeMenuTrail.length > 0 ? activeMenuTrail[activeMenuTrail.length - 1].label : null;
  const selectedMenuKey = activeMenuTrail.length > 0 ? activeMenuTrail[activeMenuTrail.length - 1].key : location.pathname;
  const breadcrumbText = activeMenuTrail.length > 1 ? activeMenuTrail.map((menu) => menu.label).join(' / ') : '后台总览';

  const handleChangePassword = async () => {
    const values = await passwordForm.validateFields();
    setPasswordSubmitting(true);
    try {
      await changePasswordRequest({
        oldPassword: values.oldPassword,
        newPassword: values.newPassword,
      });
      message.success('密码修改成功，请重新登录');
      passwordForm.resetFields();
      setPasswordModalOpen(false);
      logout();
      navigate('/login', { replace: true });
    } finally {
      setPasswordSubmitting(false);
    }
  };

  const userItems: MenuProps['items'] = [
    {
      key: 'change-password',
      icon: <LockOutlined />,
      label: '修改密码',
      onClick: () => {
        passwordForm.resetFields();
        setPasswordModalOpen(true);
      },
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout();
        navigate('/login', { replace: true });
      },
    },
  ];

  const sidebar = (
    <SidebarContent
      menuItems={menuItems}
      selectedMenuKey={selectedMenuKey}
      openKeys={openKeys}
      onOpenChange={setManualOpenKeys}
      collapsed={isDesktop && sidebarCollapsed}
      onToggleCollapsed={handleToggleSidebar}
      showToggle={isDesktop}
    />
  );

  const currentSidebarWidth = sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <Layout className="min-h-screen bg-[#eef3f1] font-sans antialiased">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(20,184,166,0.10),transparent_28%),radial-gradient(circle_at_86%_4%,rgba(13,148,136,0.06),transparent_25%),linear-gradient(135deg,#f8fafc_0%,#eef6f3_55%,#edf1f7_100%)]" />

      {isDesktop ? (
        <Sider
          width={SIDEBAR_WIDTH}
          collapsedWidth={SIDEBAR_COLLAPSED_WIDTH}
          collapsed={sidebarCollapsed}
          trigger={null}
          theme="dark"
          className="!fixed !bottom-0 !left-0 !top-0 !z-50 overflow-hidden !bg-[#0f172a] shadow-[8px_0_24px_rgba(15,23,42,0.10)] transition-all duration-300"
        >
          {sidebar}
        </Sider>
      ) : (
        <Drawer
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          placement="left"
          width={Math.min(SIDEBAR_WIDTH, Math.max(windowWidth - 48, 240))}
          closable={false}
          styles={{
            body: { padding: 0, background: '#0f172a' },
            content: { background: '#0f172a' },
          }}
        >
          {sidebar}
        </Drawer>
      )}

      <Layout
        className="relative z-10 min-h-screen bg-transparent transition-[margin-left] duration-300"
        style={{ marginLeft: isDesktop ? currentSidebarWidth : 0 }}
      >
        <Header className="sticky top-0 z-40 !h-auto !border-b !border-slate-200/60 !bg-white/85 !px-3 !py-3 !leading-none backdrop-blur-xl sm:!px-4 sm:!py-3 lg:!px-8">
          <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-2 sm:gap-4">
            <div className="flex min-w-0 items-center gap-2 sm:gap-3">
              {!isDesktop ? (
                <Button
                  type="text"
                  aria-label="打开导航菜单"
                  icon={<MenuOutlined />}
                  className="!h-9 !w-9 shrink-0 !rounded-lg !text-slate-600"
                  onClick={() => setMobileMenuOpen(true)}
                />
              ) : null}
              <div className="min-w-0">
                {breadcrumbText ? (
                  <div className="mb-0.5 hidden truncate text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400 sm:block">
                    {breadcrumbText}
                  </div>
                ) : null}
                <Typography.Title level={3} className="!mb-0 !truncate !text-base !font-semibold !tracking-normal !text-slate-900 sm:!text-lg lg:!text-xl">
                  {currentMenuLabel || '设备管理中心'}
                </Typography.Title>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2 sm:gap-2.5">
              <div className="hidden rounded-lg border border-slate-200 bg-white/70 px-3 py-1.5 text-right xl:block">
                <div className="text-[13px] font-semibold tabular-nums text-slate-900 leading-tight">{now.format('HH:mm')}</div>
                <div className="mt-0.5 text-[11px] tabular-nums text-slate-500">{now.format('YYYY-MM-DD')}</div>
              </div>

              <div className="hidden items-center gap-1.5 rounded-lg border border-emerald-100 bg-emerald-50/70 px-2.5 py-1.5 text-[13px] font-medium text-emerald-700 lg:flex">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                <span className="hidden xl:inline">运行正常</span>
                <span className="xl:hidden">正常</span>
              </div>

              <Dropdown menu={{ items: userItems }} placement="bottomRight" arrow>
                <button type="button" className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white/80 px-1.5 py-1 text-left transition hover:border-teal-300 hover:bg-teal-50/50 sm:gap-2.5 sm:pl-2 sm:pr-3">
                  <Avatar size={32} className="!bg-gradient-to-br !from-teal-600 !to-teal-700 !font-semibold !text-white">
                    {username?.[0] || 'A'}
                  </Avatar>
                  <span className="hidden min-w-0 sm:block">
                    <span className="block max-w-32 truncate text-[13px] font-semibold leading-tight text-slate-900">
                      {username || 'admin'}
                    </span>
                    <span className="mt-0.5 block max-w-32 truncate text-[11px] text-slate-500">
                      {role?.name || '控制台用户'}
                    </span>
                  </span>
                </button>
              </Dropdown>
            </div>
          </div>
        </Header>

        <Content className="px-3 py-4 sm:px-4 sm:py-5 lg:px-8 lg:py-6">
          <div className="mx-auto max-w-[1600px]">
            <Outlet />
          </div>
        </Content>
      </Layout>

      <Modal
        title="修改密码"
        open={passwordModalOpen}
        okText="确认修改"
        cancelText="取消"
        confirmLoading={passwordSubmitting}
        destroyOnHidden
        onCancel={() => {
          setPasswordModalOpen(false);
          passwordForm.resetFields();
        }}
        onOk={() => void handleChangePassword()}
      >
        <Form form={passwordForm} layout="vertical" preserve={false} className="pt-2">
          <Form.Item
            name="oldPassword"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password autoComplete="current-password" placeholder="请输入当前登录密码" />
          </Form.Item>

          <Form.Item
            name="newPassword"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '新密码至少 8 位' },
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="请输入新密码" />
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
            <Input.Password autoComplete="new-password" placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
};
