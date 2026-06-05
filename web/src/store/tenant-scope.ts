import { create } from 'zustand';

// 平台超管「按公司浏览」时的当前公司作用域。
// 仅在 /tenants/:tenantId/* 业务路由挂载时写入，离开时清空；
// 请求拦截器通过 useTenantScopeStore.getState().tenantId 读取（非订阅，避免闭包陈旧）。
type TenantScopeState = {
  tenantId: number | null;
  includeHiddenTenants: boolean;
  setTenantId: (tenantId: number | null) => void;
  setIncludeHiddenTenants: (includeHiddenTenants: boolean) => void;
  clear: () => void;
};

export const useTenantScopeStore = create<TenantScopeState>((set) => ({
  tenantId: null,
  includeHiddenTenants: false,
  setTenantId: (tenantId) => set({ tenantId }),
  setIncludeHiddenTenants: (includeHiddenTenants) => set({ includeHiddenTenants }),
  clear: () => set({ tenantId: null }),
}));
