import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const apiProxyTarget = env.VITE_API_PROXY_TARGET;

  return {
    plugins: [react()],
    build: {
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.replace(/\\/g, '/');
            const nodeModulesIndex = normalizedId.indexOf('/node_modules/');
            if (nodeModulesIndex === -1) {
              return undefined;
            }

            const packagePath = normalizedId.slice(nodeModulesIndex + '/node_modules/'.length);
            const packageName = packagePath.indexOf('@') === 0
              ? packagePath.split('/').slice(0, 2).join('/')
              : packagePath.split('/')[0];

            if (packageName === 'echarts') {
              return 'echarts';
            }
            if (packageName === 'zrender') {
              return 'zrender';
            }
            if (['react', 'react-dom', 'react-router', 'react-router-dom', '@remix-run/router', 'scheduler'].indexOf(packageName) >= 0) {
              return 'react-vendor';
            }
            if (
              packageName === 'antd' ||
              packageName.indexOf('@ant-design/cssinjs') === 0 ||
              packageName === '@ant-design/colors' ||
              packageName === '@ant-design/icons' ||
              packageName === '@ant-design/icons-svg'
            ) {
              return 'antd';
            }
            if (packageName.indexOf('rc-') === 0 || packageName.indexOf('@rc-component/') === 0) {
              return 'antd-rc';
            }

            return 'vendor';
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      proxy: apiProxyTarget
        ? {
            '/api': {
              target: apiProxyTarget,
              changeOrigin: true,
            },
            '/media': {
              target: apiProxyTarget,
              changeOrigin: true,
            },
            '/static': {
              target: apiProxyTarget,
              changeOrigin: true,
            },
            '/ws': {
              target: apiProxyTarget,
              ws: true,
              changeOrigin: true,
            },
          }
        : undefined,
    },
  };
});
