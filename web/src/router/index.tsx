import { useEffect, type ReactNode } from 'react';
import { Navigate, useRoutes } from 'react-router-dom';
import { Spin } from 'antd';
import {
  CommandExportManagementPage,
  CommandWorkspacePage,
  PointManagementPage,
} from '../views/command-management';
import { LoginPage } from '../views/login';
import { DashboardLayout } from '../layouts/dashboard-layout';
import { DeviceManagementPage } from '../views/device-management';
import { AccountApplicationsPage } from '../views/account-applications/index';
import { ModelManagementPage } from '../views/model-management';
import { ResourceManagementPage } from '../views/resource-management';
import { ScrollingTextManagementPage } from '../views/scrolling-text-management';
import { KnowledgeBasePage } from '../views/knowledge-base';
import { VoiceToneManagementPage } from '../views/voice-tone-management';
import { AsrManagementPage } from '../views/asr-management';
import { LlmManagementPage } from '../views/llm-management';
import { TtsManagementPage } from '../views/tts-management';
import { ChatRoomPage } from '../views/chat-room';
import { TenantManagementPage } from '../views/tenant-management';
import { EmployeeManagementPage } from '../views/employee-management';
import { ForcePasswordChangePage } from '../views/force-password-change';
import { fetchCurrentUser } from '../api/modules/auth';
import { useAuthStore } from '../store/auth';

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
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (!token) {
    return <>{children}</>;
  }

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  return <Navigate to={getFirstAccessiblePath(menus)} replace />;
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

const DefaultAuthedRoute = () => {
  const menus = useAuthStore((state) => state.menus);
  const authSyncStatus = useAuthStore((state) => state.authSyncStatus);

  if (authSyncStatus !== 'ready') {
    return <AuthSyncFallback />;
  }

  return <Navigate to={getFirstAccessiblePath(menus)} replace />;
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
        {
          path: 'ai-models/chat',
          element: (
            <PermissionGuard permission="ai_models.chat.view">
              <ChatRoomPage />
            </PermissionGuard>
          ),
        },
      ],
    },
    { path: '*', element: <DefaultAuthedRoute /> },
  ]);

  return elements;
};
