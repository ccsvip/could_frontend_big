import React from 'react';

export type StatusType =
  | 'online'
  | 'offline'
  | 'active'
  | 'inactive'
  | 'bound'
  | 'unbound'
  | 'pending';

export interface StatusTagProps {
  type: StatusType;
  label?: string;
  className?: string;
  showDot?: boolean;
}

const STATUS_CONFIG: Record<
  StatusType,
  { defaultLabel: string; bgClass: string; textClass: string; borderClass: string; dotClass: string }
> = {
  online: {
    defaultLabel: '在线',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-700',
    borderClass: 'border-emerald-200',
    dotClass: 'bg-emerald-500',
  },
  offline: {
    defaultLabel: '离线',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-500',
    borderClass: 'border-slate-200',
    dotClass: 'bg-slate-400',
  },
  active: {
    defaultLabel: '已启用',
    bgClass: 'bg-brand-50',
    textClass: 'text-brand-700',
    borderClass: 'border-brand-200',
    dotClass: 'bg-brand-600',
  },
  inactive: {
    defaultLabel: '已停用',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-500',
    borderClass: 'border-slate-200',
    dotClass: 'bg-slate-400',
  },
  bound: {
    defaultLabel: '已绑定',
    bgClass: 'bg-brand-50',
    textClass: 'text-brand-700',
    borderClass: 'border-brand-200',
    dotClass: 'bg-brand-600',
  },
  unbound: {
    defaultLabel: '未绑定',
    bgClass: 'bg-slate-50',
    textClass: 'text-slate-400',
    borderClass: 'border-slate-200',
    dotClass: 'bg-slate-300',
  },
  pending: {
    defaultLabel: '处理中',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-700',
    borderClass: 'border-blue-200',
    dotClass: 'bg-blue-500 animate-pulse',
  },
};

export const StatusTag: React.FC<StatusTagProps> = ({
  type,
  label,
  className = '',
  showDot = true,
}) => {
  const config = STATUS_CONFIG[type] || STATUS_CONFIG.offline;
  const displayLabel = label || config.defaultLabel;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-fluid-xs font-medium ${config.bgClass} ${config.textClass} ${config.borderClass} ${className}`}
    >
      {showDot && (
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${config.dotClass}`} />
      )}
      <span>{displayLabel}</span>
    </span>
  );
};
