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
            if (normalizedId.indexOf('/node_modules/') === -1) {
              return undefined;
            }

            if (normalizedId.indexOf('/antd/') >= 0) {
              return 'antd';
            }
            if (normalizedId.indexOf('/@ant-design/icons/') >= 0) {
              return 'antd-icons';
            }
            if (
              normalizedId.indexOf('/axios/') >= 0 ||
              normalizedId.indexOf('/dayjs/') >= 0 ||
              normalizedId.indexOf('/zustand/') >= 0
            ) {
              return 'vendor';
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
              changeOrigin: false,
            },
            '/media': {
              target: apiProxyTarget,
              changeOrigin: true,
            },
            '/ws': {
              target: apiProxyTarget,
              ws: true,
              changeOrigin: false,
            },
          }
        : undefined,
    },
  };
});
