import { RobotOutlined } from '@ant-design/icons';

type BrandMarkProps = {
  title: string;
  subtitle?: string;
  tone?: 'light' | 'dark';
  compact?: boolean;
  className?: string;
};

export const BrandMark = ({ title, subtitle, tone = 'light', compact = false, className = '' }: BrandMarkProps) => {
  const titleColor = tone === 'dark' ? 'text-white' : 'text-slate-900';
  const subtitleColor = tone === 'dark' ? 'text-slate-400' : 'text-slate-500';
  const iconShell =
    tone === 'dark'
      ? 'border-white/10 bg-gradient-to-br from-teal-500/30 to-teal-700/20 text-teal-200'
      : 'border-teal-100 bg-gradient-to-br from-teal-50 to-white text-teal-700 shadow-[0_4px_12px_rgba(15,118,110,0.12)]';

  return (
    <div className={`flex min-w-0 items-center gap-3 ${className}`}>
      {/* 品牌图标用于登录页与后台框架保持一致识别，不绑定具体业务路由。 */}
      <div
        className={`flex shrink-0 items-center justify-center rounded-xl border ${iconShell} ${
          compact ? 'h-10 w-10' : 'h-11 w-11'
        }`}
      >
        <RobotOutlined className={compact ? 'text-lg' : 'text-xl'} />
      </div>
      <div className="min-w-0">
        <div className={`truncate font-semibold tracking-tight ${titleColor} ${compact ? 'text-[14px]' : 'text-[15px]'}`}>
          {title}
        </div>
        {subtitle ? (
          <div className={`mt-0.5 truncate text-[11px] font-medium uppercase tracking-[0.12em] ${subtitleColor}`}>
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
};
