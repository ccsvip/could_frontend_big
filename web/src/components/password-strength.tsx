import { useMemo } from 'react';

type StrengthLevel = 'weak' | 'medium' | 'good' | 'strong';

interface PasswordStrengthProps {
  password: string;
}

const CONDITIONS = [
  (p: string) => p.length >= 8,
  (p: string) => /[A-Z]/.test(p),
  (p: string) => /[a-z]/.test(p),
  (p: string) => /[0-9]/.test(p),
  (p: string) => /[^A-Za-z0-9]/.test(p),
];

const LEVEL_MAP: Record<number, StrengthLevel> = {
  0: 'weak',
  1: 'weak',
  2: 'medium',
  3: 'good',
  4: 'strong',
  5: 'strong',
};

const LEVEL_LABEL: Record<StrengthLevel, string> = {
  weak: '弱',
  medium: '中',
  good: '良',
  strong: '强',
};

export function PasswordStrength({ password }: PasswordStrengthProps) {
  const level = useMemo(() => {
    if (!password) return null;
    const passed = CONDITIONS.filter((fn) => fn(password)).length;
    return LEVEL_MAP[passed];
  }, [password]);

  if (!level) return null;

  const activeCount = CONDITIONS.filter((fn) => fn(password)).length;

  return (
    <div className="password-strength" role="status" aria-label={`密码强度：${LEVEL_LABEL[level]}`}>
      <div className="password-strength__bar">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={[
              'password-strength__segment',
              i < activeCount ? 'password-strength__segment--active' : '',
              i < activeCount ? `password-strength__segment--${level}` : '',
            ].filter(Boolean).join(' ')}
          />
        ))}
      </div>
      <span className={`password-strength__label password-strength__label--${level}`}>
        {LEVEL_LABEL[level]}
      </span>
    </div>
  );
}
