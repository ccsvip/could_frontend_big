import React from 'react';
import { Dropdown, MenuProps } from 'antd';
import { useTranslation } from 'react-i18next';
import { IconLanguage } from '@tabler/icons-react';

export const LanguageSelector: React.FC<{ className?: string }> = ({ className }) => {
  const { i18n } = useTranslation();

  const items: MenuProps['items'] = [
    {
      key: 'zh-CN',
      label: '简体中文',
      onClick: () => i18n.changeLanguage('zh-CN'),
    },
    {
      key: 'en-US',
      label: 'English',
      onClick: () => i18n.changeLanguage('en-US'),
    },
    {
      key: 'km-KH',
      label: 'ភាសាខ្មែរ',
      onClick: () => i18n.changeLanguage('km-KH'),
    },
    {
      key: 'vi-VN',
      label: 'Tiếng Việt',
      onClick: () => i18n.changeLanguage('vi-VN'),
    },
  ];

  return (
    <Dropdown menu={{ items, selectedKeys: [i18n.language] }} placement="bottomRight" arrow>
      <button
        type="button"
        className={`flex items-center justify-center rounded-lg border border-slate-200 bg-white/80 p-1.5 transition hover:border-brand-300 hover:bg-brand-50/50 text-slate-600 hover:text-brand-600 ${className || ''}`}
        title="切换语言 / Switch Language"
      >
        <IconLanguage size={20 as any} stroke={1.5 as any} />
      </button>
    </Dropdown>
  );
};
