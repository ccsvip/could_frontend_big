import { lazy, Suspense, useEffect, type ReactNode } from 'react';
import { Navigate, Outlet, useParams, useRoutes } from 'react-router-dom';
import { Spin } from 'antd';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { fetchCurrentUser } from '../api/modules/auth';
import { useAuthStore } from '../store/auth';
import { useTenantScopeStore } from '../store/tenant-scope';

const LoginPage = lazy(() => import('../views/login').then((module) => ({ default: module.LoginPage })));
const DeviceManagementPage = lazy(() =>
  import('../views/device-management').then((module) => ({ default: module.DeviceManagementPage })),
);
const DeviceAuthorizationCenterPage = lazy(() =>
  import('../views/device-authorization-center').then((module) => ({
    default: module.DeviceAuthorizationCenterPage,
  })),
);
const AccountApplicationsPage = lazy(() =>
  import('../views/account-applications').then((module) => ({ default: module.AccountApplicationsPage })),
);
const ModelManagementPage = lazy(() =>
  import('../views/model-management').then((module) => ({ default: module.ModelManagementPage })),
);
const ResourceManagementPage = lazy(() =>
  import('../views/resource-management').then((module) => ({ default: module.ResourceManagementPage })),
);
const ScrollingTextManagementPage = lazy(() =>
  import('../views/scrolling-text-management').then((module) => ({
    default: module.ScrollingTextManagementPage,
  })),
);
const KnowledgeBasePage = lazy(() =>
  import('../views/knowledge-base').then((module) => ({ default: module.KnowledgeBasePage })),
);
const VoiceToneManagementPage = lazy(() =>
  import('../views/voice-tone-management').then((module) => ({ default: module.VoiceToneManagementPage })),
);
const AsrManagementPage = lazy(() =>
  import('../views/asr-management').then((module) => ({ default: module.AsrManagementPage })),
);
const LlmManagementPage = lazy(() =>
  import('../views/llm-management').then((module) => ({ default: module.LlmManagementPage })),
);
const TtsManagementPage = lazy(() =>
  import('../views/tts-management').then((module) => ({ default: module.TtsManagementPage })),
);
const ApplicationManagementPage = lazy(() =>
  import('../views/application-management').then((module) => ({ default: module.ApplicationManagementPage })),
);
const TenantManagementPage = lazy(() =>
  import('../views/tenant-management').then((module) => ({ default: module.TenantManagementPage })),
);
const EmployeeManagementPage = lazy(() =>
  import('../views/employee-management').then((module) => ({ default: module.EmployeeManagementPage })),
);
const ForcePasswordChangePage = lazy(() =>
  import('../views/force-password-change').then((module) => ({ default: module.ForcePasswordChangePage })),
);
const LogManagementPage = lazy(() =>
  import('../views/log-management').then((module) => ({ default: module.LogManagementPage })),
);
const MinioSettingsPage = lazy(() =>
  import('../views/minio-settings').then((module) => ({ default: module.MinioSettingsPage })),
);
const AsrSettingsPage = lazy(() =>
  import('../views/asr-settings').then((module) => ({ default: module.AsrSettingsPage })),
);
const TtsSettingsPage = lazy(() =>
  import('../views/tts-settings').then((module) => ({ default: module.TtsSettingsPage })),
);
const LlmSettingsAdminPage = lazy(() =>
  import('../views/settings-llm').then((module) => ({ default: module.LlmSettingsAdminPage })),
);
const CommandWorkspacePage = lazy(() =>
  import('../views/command-management/workspace').then((module) => ({ default: module.CommandWorkspacePage })),
);
const PointManagementPage = lazy(() =>
  import('../views/command-management/points').then((module) => ({ default: module.PointManagementPage })),
);
const CommandExportManagementPage = lazy(() =>
  import('../views/command-management/export').then((module) => ({ default: module.CommandExportManagementPage })),
);

let inFlightSyncToken: string | null = null;
let inFlightSyncPromise: Promise<void> | null = null;

type RouteMenu = {
  key: string;
  path?: string;
  children?: RouteMenu[];
};

const hiddenRouteMenuPaths = new Set(['/commands/task-lists', 'commands/task-lists']);

const filterRouteMenus = (menus: RouteMenu[]): RouteMenu[] => {
  return menus
    .filter((menu) => !hiddenRouteMenuPaths.has(menu.path || menu.key))
    .map((menu) => {
      const children = menu.children ? filterRouteMenus(menu.children) : undefined;
      return {
        ...menu,
        children: children && children.length > 0 ? children : undefined,
      };
    });
};

const getFirstAccessiblePath = (menus: RouteMenu[]) => {
  // 默认跳转同样跳过已下线的任务列表二级菜单。
  const stack = filterRouteMenus(menus);

  while (stack.length > 0) {
    const current = stack.shift();
    if (!current) {
      continue;
    }

    if (current.children && current.children.length > 0) {
      stack.unshift(...current.children);
      continue;
    }

    return current.path || current.key;
  }

  return '/login';
};

// 平台超管（持 tenant.management.view）默认落地「租户管理」页，不走后端 menus 流程。
const resolveLandingPath = (hasPermission: (permission: string) => boolean, menus: RouteMenu[]) => {
  if (hasPermission('tenant.management.view')) {
    return '/tenants';
  }
  return getFirstAccessiblePath(menus);
};

// 在 /tenants/:tenantId/* 业务路由挂载期间写入公司作用域，离开时清空。
// axios 请求拦截器据此为业务接口追加 ?tenant=<id>。
const TenantScopeOutlet = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const setTenantId = useTenantScopeStore((state) => state.setTenantId);
  const clear = useTenantScopeStore((state) => state.clear);

  useEffect(() => {
    const parsed = Number(tenantId);
    setTenantId(Number.isFinite(parsed) && parsed > 0 ? parsed : null);
    return () => {
      clear();
    };
  }, [tenantId, setTenantId, clear]);

  return <Outlet />;
};

const AuthSyncFallback = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-50">
    <div className="flex flex-col items-center gap-3 text-slate-500">
      <Spin size="large" />
      <span>正在同步权限信息</span>
    </div>
  </div>
);

const AuthGuard = ({ children }: { children: ReactNode }) => {
  const token = useAuthStore((state) => state.token);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);
  const mustChangePassword = useAuthStore((state) => state.mustChangePassword);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  // 首登 / 被重置密码的员工必须先改密，挡住所有业务页面。
  if (mustChangePassword) {
    return <ForcePasswordChangePage />;
  }

  return <>{children}</>;
};

const GuestGuard = ({ children }: { children: ReactNode }) => {
  const token = useAuthStore((state) => state.token);
  const menus = useAuthStore((state) => state.menus);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (!token) {
    return <>{children}</>;
  }

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  return <Navigate to={resolveLandingPath(hasPermission, menus)} replace />;
};

const PermissionGuard = ({ children, permission }: { children: ReactNode; permission?: string }) => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const menus = useAuthStore((state) => state.menus);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  if (!permission || hasPermission(permission)) {
    return <>{children}</>;
  }

  return <Navigate to={getFirstAccessiblePath(menus)} replace />;
};

const AuditLogGuard = ({ children }: { children: ReactNode }) => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const menus = useAuthStore((state) => state.menus);
  const tenant = useAuthStore((state) => state.tenant);
  const isSuperuser = useAuthStore((state) => state.isSuperuser);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  if (hasPermission('audit.logs.view') && (isSuperuser || tenant?.isTenantAdmin)) {
    return <>{children}</>;
  }

  return <Navigate to={getFirstAccessiblePath(menus)} replace />;
};

const DefaultAuthedRoute = () => {
  const menus = useAuthStore((state) => state.menus);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  return <Navigate to={resolveLandingPath(hasPermission, menus)} replace />;
};

export const AppRouter = () => {
  const token = useAuthStore((state) => state.token);
  const setUserContext = useAuthStore((state) => state.setUserContext);
  const setAuthSyncStatus = useAuthStore((state) => state.setAuthSyncStatus);

  useEffect(() => {
    if (!token) {
      inFlightSyncToken = null;
      inFlightSyncPromise = null;
      setAuthSyncStatus('ready');
      return;
    }

    if (inFlightSyncToken === token && inFlightSyncPromise) {
      return;
    }

    setAuthSyncStatus('syncing');

    const syncPromise = fetchCurrentUser()
      .then((currentUser) => {
        setUserContext({
          username: currentUser.display_name || currentUser.username,
          role: currentUser.role,
          permissions: currentUser.permissions,
          menus: currentUser.menus,
          tenant: currentUser.tenant,
          isSuperuser: currentUser.is_superuser,
          mustChangePassword: currentUser.must_change_password,
        });
      })
      .catch(() => {
        // 401 仍由 axios 响应拦截器统一清理，这里只保证守卫状态收敛。
      })
      .finally(() => {
        if (inFlightSyncToken === token) {
          inFlightSyncPromise = null;
        }
        setAuthSyncStatus('ready');
      });

    inFlightSyncToken = token;
    inFlightSyncPromise = syncPromise;
  }, [token, setAuthSyncStatus, setUserContext]);

  const elements = useRoutes([
    {
      path: '/login',
      element: (
        <GuestGuard>
          <LoginPage />
        </GuestGuard>
      ),
    },
    {
      path: '/',
      element: (
        <AuthGuard>
          <DashboardLayout />
        </AuthGuard>
      ),
      children: [
        { index: true, element: <DefaultAuthedRoute /> },
        {
          path: 'tenants',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <TenantManagementPage />
            </PermissionGuard>
          ),
        },
        {
          // 平台超管「按公司浏览」业务作用域：挂载期间写入 tenant-scope store，
          // axios 拦截器据此为业务接口注入 ?tenant=<id>。所有子路由复用现有业务页面组件。
          path: 'tenants/:tenantId',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <TenantScopeOutlet />
            </PermissionGuard>
          ),
          children: [
            { index: true, element: <Navigate to="devices" replace /> },
            { path: 'devices', element: <DeviceManagementPage /> },
            { path: 'resources', element: <Navigate to="resources/images" replace /> },
            { path: 'resources/images', element: <ResourceManagementPage key="scoped-resource-image" resourceType="image" /> },
            { path: 'resources/videos', element: <ResourceManagementPage key="scoped-resource-video" resourceType="video" /> },
            { path: 'resources/scrolling-texts', element: <ScrollingTextManagementPage /> },
            { path: 'resources/voice-tones', element: <VoiceToneManagementPage /> },
            { path: 'resources/models', element: <ModelManagementPage /> },
            { path: 'knowledge-base', element: <KnowledgeBasePage /> },
            { path: 'applications', element: <ApplicationManagementPage /> },
            { path: 'applications/:applicationId', element: <ApplicationManagementPage /> },
            { path: 'commands', element: <CommandWorkspacePage /> },
            { path: 'ai-models', element: <Navigate to="ai-models/llm" replace /> },
            { path: 'ai-models/asr', element: <AsrManagementPage /> },
            { path: 'ai-models/llm', element: <LlmManagementPage /> },
            { path: 'ai-models/tts', element: <TtsManagementPage /> },
          ],
        },
        {
          path: 'device-authorizations',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <DeviceAuthorizationCenterPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'settings/minio',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <MinioSettingsPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'settings/asr',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <AsrSettingsPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'settings/tts',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <TtsSettingsPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'settings/tts/:providerCode',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <TtsSettingsPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'settings/llm',
          element: (
            <PermissionGuard permission="tenant.management.view">
              <LlmSettingsAdminPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'logs',
          element: (
            <AuditLogGuard>
              <LogManagementPage />
            </AuditLogGuard>
          ),
        },
        {
          path: 'employees',
          element: (
            <PermissionGuard permission="tenant.employees.manage">
              <EmployeeManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'knowledge-base',
          element: (
            <PermissionGuard permission="knowledge_base.view">
              <KnowledgeBasePage />
            </PermissionGuard>
          ),
        },
        {
          path: 'applications',
          element: (
            <PermissionGuard permission="agent_applications.view">
              <ApplicationManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'applications/:applicationId',
          element: (
            <PermissionGuard permission="agent_applications.view">
              <ApplicationManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'devices',
          element: (
            <PermissionGuard permission="devices.view">
              <DeviceManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'account-applications',
          element: (
            <PermissionGuard permission="account_applications.view">
              <AccountApplicationsPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'commands/groups',
          element: (
            <PermissionGuard permission="commands.groups.view">
              <CommandWorkspacePage />
            </PermissionGuard>
          ),
        },
        {
          path: 'commands/control',
          element: (
            <PermissionGuard permission="commands.control.view">
              <CommandWorkspacePage />
            </PermissionGuard>
          ),
        },
        {
          path: 'commands/tasks',
          element: (
            <PermissionGuard permission="commands.tasks.view">
              <CommandWorkspacePage />
            </PermissionGuard>
          ),
        },
        {
          path: 'commands/points',
          element: (
            <PermissionGuard permission="commands.points.view">
              <PointManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'commands/export',
          element: (
            <PermissionGuard permission="commands.export.view">
              <CommandExportManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'resources/images',
          element: (
            <PermissionGuard permission="resources.images.view">
              <ResourceManagementPage key="resource-image" resourceType="image" />
            </PermissionGuard>
          ),
        },
        {
          path: 'resources/videos',
          element: (
            <PermissionGuard permission="resources.videos.view">
              <ResourceManagementPage key="resource-video" resourceType="video" />
            </PermissionGuard>
          ),
        },
        {
          path: 'resources/scrolling-texts',
          element: (
            <PermissionGuard permission="resources.scrolling_texts.view">
              <ScrollingTextManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'resources/voice-tones',
          element: (
            <PermissionGuard permission="resources.voice_tones.view">
              <VoiceToneManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'resources/models',
          element: (
            <PermissionGuard permission="resources.models.view">
              <ModelManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'ai-models/asr',
          element: (
            <PermissionGuard permission="ai_models.asr.view">
              <AsrManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'ai-models/llm',
          element: (
            <PermissionGuard permission="ai_models.llm.view">
              <LlmManagementPage />
            </PermissionGuard>
          ),
        },
        {
          path: 'ai-models/tts',
          element: (
            <PermissionGuard permission="ai_models.tts.view">
              <TtsManagementPage />
            </PermissionGuard>
          ),
        },
      ],
    },
    { path: '*', element: <DefaultAuthedRoute /> },
  ]);

  return <Suspense fallback={<AuthSyncFallback />}>{elements}</Suspense>;
};
