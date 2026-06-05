import { create } from 'zustand';

export type AppRole = {
  code: string;
  name: string;
} | null;

export type AppMenu = {
  key: string;
  label: string;
  icon?: string;
  path?: string;
  children?: AppMenu[];
};

export type AppTenant = {
  id: number;
  name: string;
  code: string;
  isTenantAdmin: boolean;
} | null;

export type AuthSyncStatus = 'idle' | 'syncing' | 'ready';

type LoginPayload = {
  username: string;
  token: string;
  refreshToken: string;
  role: AppRole;
  permissions: string[];
  menus: AppMenu[];
  tenant: AppTenant;
  isSuperuser: boolean;
  mustChangePassword: boolean;
};

type UserContextPayload = Omit<LoginPayload, 'token' | 'refreshToken'>;

type AuthState = {
  token: string | null;
  refreshToken: string | null;
  username: string;
  role: AppRole;
  permissions: string[];
  menus: AppMenu[];
  tenant: AppTenant;
  isSuperuser: boolean;
  mustChangePassword: boolean;
  authSyncStatus: AuthSyncStatus;
  login: (payload: LoginPayload) => void;
  setUserContext: (payload: UserContextPayload) => void;
  setAuthSyncStatus: (status: AuthSyncStatus) => void;
  logout: () => void;
  clearAuth: () => void;
  hasPermission: (permission: string) => boolean;
};

const TOKEN_STORAGE_KEY = 'token';
const REFRESH_TOKEN_STORAGE_KEY = 'refreshToken';
const USERNAME_STORAGE_KEY = 'username';
const ROLE_STORAGE_KEY = 'role';
const PERMISSIONS_STORAGE_KEY = 'permissions';
const MENUS_STORAGE_KEY = 'menus';
const TENANT_STORAGE_KEY = 'tenant';
const IS_SUPERUSER_STORAGE_KEY = 'isSuperuser';
const MUST_CHANGE_PASSWORD_STORAGE_KEY = 'mustChangePassword';

const readStoredJson = <T>(key: string, fallback: T): T => {
  const value = localStorage.getItem(key);
  if (!value) {
    return fallback;
  }

  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
};

const readStoredRole = (): AppRole => {
  const value = localStorage.getItem(ROLE_STORAGE_KEY);
  if (!value) {
    return null;
  }

  try {
    const parsed = JSON.parse(value) as unknown;

    if (
      parsed &&
      typeof parsed === 'object' &&
      'code' in parsed &&
      typeof (parsed as { code: unknown }).code === 'string'
    ) {
      const role = parsed as { code: string; name?: unknown };
      return {
        code: role.code,
        name: typeof role.name === 'string' ? role.name : role.code,
      };
    }

    return null;
  } catch {
    return null;
  }
};

const readStoredPermissions = () => {
  const parsed = readStoredJson<unknown>(PERMISSIONS_STORAGE_KEY, []);
  return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
};

const readStoredMenus = (): AppMenu[] => {
  const parseMenu = (item: unknown): AppMenu | null => {
    if (!item || typeof item !== 'object') {
      return null;
    }

    const record = item as Record<string, unknown>;
    const children = Array.isArray(record.children)
      ? record.children.map((child) => parseMenu(child)).filter((child): child is AppMenu => Boolean(child))
      : undefined;

    const parsedMenu: AppMenu = {
      key: typeof record.key === 'string' ? record.key : '',
      label: typeof record.label === 'string' ? record.label : '',
      icon: typeof record.icon === 'string' ? record.icon : undefined,
      path: typeof record.path === 'string' ? record.path : undefined,
      children: children && children.length > 0 ? children : undefined,
    };

    return parsedMenu.key && parsedMenu.label ? parsedMenu : null;
  };

  const parsed = readStoredJson<unknown>(MENUS_STORAGE_KEY, []);
  if (!Array.isArray(parsed)) {
    return [];
  }

  return parsed.map((item) => parseMenu(item)).filter((item): item is AppMenu => Boolean(item));
};

const persistUserContext = ({ username, role, permissions, menus, tenant, isSuperuser, mustChangePassword }: UserContextPayload) => {
  localStorage.setItem(USERNAME_STORAGE_KEY, username);
  localStorage.setItem(ROLE_STORAGE_KEY, JSON.stringify(role));
  localStorage.setItem(PERMISSIONS_STORAGE_KEY, JSON.stringify(permissions));
  localStorage.setItem(MENUS_STORAGE_KEY, JSON.stringify(menus));
  localStorage.setItem(TENANT_STORAGE_KEY, JSON.stringify(tenant));
  localStorage.setItem(IS_SUPERUSER_STORAGE_KEY, JSON.stringify(isSuperuser));
  localStorage.setItem(MUST_CHANGE_PASSWORD_STORAGE_KEY, JSON.stringify(mustChangePassword));
};

const readStoredTenant = (): AppTenant => {
  const parsed = readStoredJson<unknown>(TENANT_STORAGE_KEY, null);
  if (
    parsed &&
    typeof parsed === 'object' &&
    'id' in parsed &&
    'code' in parsed
  ) {
    const t = parsed as { id: number; name?: unknown; code: string; isTenantAdmin?: unknown };
    return {
      id: t.id,
      name: typeof t.name === 'string' ? t.name : '',
      code: t.code,
      isTenantAdmin: Boolean(t.isTenantAdmin),
    };
  }
  return null;
};

const readStoredMustChangePassword = (): boolean => {
  return readStoredJson<boolean>(MUST_CHANGE_PASSWORD_STORAGE_KEY, false) === true;
};

const clearAuthStorage = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  localStorage.removeItem(USERNAME_STORAGE_KEY);
  localStorage.removeItem(ROLE_STORAGE_KEY);
  localStorage.removeItem(PERMISSIONS_STORAGE_KEY);
  localStorage.removeItem(MENUS_STORAGE_KEY);
  localStorage.removeItem(TENANT_STORAGE_KEY);
  localStorage.removeItem(IS_SUPERUSER_STORAGE_KEY);
  localStorage.removeItem(MUST_CHANGE_PASSWORD_STORAGE_KEY);
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_STORAGE_KEY),
  refreshToken: localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY),
  username: localStorage.getItem(USERNAME_STORAGE_KEY) || '',
  role: readStoredRole(),
  permissions: readStoredPermissions(),
  menus: readStoredMenus(),
  tenant: readStoredTenant(),
  isSuperuser: readStoredJson<boolean>(IS_SUPERUSER_STORAGE_KEY, false) === true,
  mustChangePassword: readStoredMustChangePassword(),
  authSyncStatus: localStorage.getItem(TOKEN_STORAGE_KEY) ? 'idle' : 'ready',
  login: ({ username, token, refreshToken, role, permissions, menus, tenant, isSuperuser, mustChangePassword }) => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
    persistUserContext({ username, role, permissions, menus, tenant, isSuperuser, mustChangePassword });
    set({ token, refreshToken, username, role, permissions, menus, tenant, isSuperuser, mustChangePassword, authSyncStatus: 'ready' });
  },
  setUserContext: ({ username, role, permissions, menus, tenant, isSuperuser, mustChangePassword }) => {
    persistUserContext({ username, role, permissions, menus, tenant, isSuperuser, mustChangePassword });
    set({ username, role, permissions, menus, tenant, isSuperuser, mustChangePassword });
  },
  setAuthSyncStatus: (authSyncStatus) => {
    set({ authSyncStatus });
  },
  logout: () => {
    clearAuthStorage();
    set({ token: null, refreshToken: null, username: '', role: null, permissions: [], menus: [], tenant: null, isSuperuser: false, mustChangePassword: false, authSyncStatus: 'ready' });
  },
  clearAuth: () => {
    clearAuthStorage();
    set({ token: null, refreshToken: null, username: '', role: null, permissions: [], menus: [], tenant: null, isSuperuser: false, mustChangePassword: false, authSyncStatus: 'ready' });
  },
  hasPermission: (permission: string) => get().permissions.includes(permission),
}));
