import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { BrowserRouter } from 'react-router-dom';
import { AppRouter } from './router';
import '@radix-ui/themes/styles.css';
import './styles/index.css';

const APP_TITLE = import.meta.env.VITE_APP_TITLE || '数字人后台管理平台';
const antdTheme = {
  token: {
    colorPrimary: '#0f766e', // 主色统一为后台工作台的青绿色
    colorInfo: '#0f766e',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    borderRadius: 10,
    borderRadiusLG: 12,
    borderRadiusSM: 8,
    colorBgBase: '#ffffff',
    colorBgLayout: '#eef3f1',
    colorTextBase: '#0f172a', // Slate 900
    colorTextSecondary: '#475569',
    colorTextTertiary: '#64748b',
    colorBorder: '#e2e8f0',
    colorBorderSecondary: '#edf2f0',
    controlHeight: 36,
    controlHeightLG: 40,
    fontSize: 14,
    lineHeight: 1.5715,
    motionDurationMid: '0.18s',
    motionDurationSlow: '0.24s',
    fontFamily:
      '"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  components: {
    Button: {
      borderRadius: 10,
      borderRadiusLG: 12,
      controlHeightLG: 42,
      fontWeight: 600,
      primaryShadow: '0 4px 12px rgba(15, 118, 110, 0.18)',
    },
    Card: {
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#edf2f0',
      borderRadiusLG: 14,
      headerFontSize: 15,
      headerHeight: 52,
      paddingLG: 20,
      boxShadowTertiary: '0 1px 2px rgba(15, 23, 42, 0.04), 0 6px 18px rgba(15, 23, 42, 0.04)',
    },
    Layout: {
      headerBg: 'rgba(255, 255, 255, 0.85)',
      bodyBg: '#eef3f1',
      headerHeight: 64,
    },
    Menu: {
      itemSelectedBg: 'rgba(20, 184, 166, 0.14)',
      itemSelectedColor: '#0f766e',
      itemHoverBg: 'rgba(20, 184, 166, 0.06)',
      itemBorderRadius: 8,
      itemHeight: 38,
    },
    Table: {
      headerBg: '#f8fafc',
      headerColor: '#334155',
      headerSplitColor: '#edf2f0',
      borderColor: '#edf2f0',
      rowHoverBg: '#f0fdfa',
      headerBorderRadius: 12,
      cellPaddingBlock: 14,
      cellPaddingInline: 16,
    },
    Modal: {
      borderRadiusLG: 14,
      titleFontSize: 16,
      paddingMD: 20,
    },
    Form: {
      labelFontSize: 14,
      labelColor: '#334155',
      verticalLabelPadding: '0 0 6px',
      itemMarginBottom: 18,
    },
    Input: {
      borderRadius: 10,
      controlHeight: 36,
      paddingInline: 12,
      activeShadow: '0 0 0 3px rgba(15, 118, 110, 0.12)',
    },
    Select: {
      borderRadius: 10,
      controlHeight: 36,
      optionSelectedBg: 'rgba(20, 184, 166, 0.10)',
      optionSelectedColor: '#0f766e',
      optionSelectedFontWeight: 600,
    },
    Tag: {
      borderRadiusSM: 6,
      defaultBg: '#f1f5f9',
      defaultColor: '#475569',
    },
    Tooltip: {
      borderRadius: 8,
      colorBgSpotlight: 'rgba(15, 23, 42, 0.92)',
    },
    Pagination: {
      borderRadius: 8,
      itemSize: 32,
    },
    Segmented: {
      borderRadius: 10,
      itemSelectedBg: '#ffffff',
      itemSelectedColor: '#0f766e',
      trackBg: '#f1f5f9',
      trackPadding: 3,
    },
    Drawer: {
      borderRadiusLG: 0,
    },
    Tabs: {
      itemSelectedColor: '#0f766e',
      itemHoverColor: '#0d9488',
      inkBarColor: '#0f766e',
      titleFontSize: 14,
    },
    Descriptions: {
      labelBg: '#f8fafc',
      titleMarginBottom: 12,
    },
    Empty: {
      colorTextDisabled: '#94a3b8',
    },
    Avatar: {
      borderRadius: 8,
    },
  },
};

document.title = APP_TITLE;

ConfigProvider.config({
  holderRender: (children) => (
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  ),
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>
        <BrowserRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
          <AppRouter />
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
);
