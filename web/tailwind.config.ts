import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // brand 是项目唯一的青绿色阶，与 antd theme 的 colorPrimary (#0f766e = brand-700) 对齐。
      // 页面写颜色一律用 brand-*；不要用 Tailwind 默认 teal-*（虽 hex 相同，但命名不在设计系统内），
      // 更不要硬写 #0f766e 字面量。
      colors: {
        brand: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
      },
      // 页面内容区统一容器：居中、有最大宽度、随断点放 padding，避免每页各写 %/px。
      container: {
        center: true,
        padding: {
          DEFAULT: '16px',
          sm: '20px',
          lg: '24px',
        },
        screens: {
          sm: '640px',
          md: '768px',
          lg: '1024px',
          xl: '1280px',
          '2xl': '1440px',
        },
      },
      boxShadow: {
        // 统一卡片阴影规格，避免每个组件各写一组数字
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 6px 18px rgba(15, 23, 42, 0.04)',
        'card-hover': '0 4px 10px rgba(15, 23, 42, 0.06), 0 12px 32px rgba(15, 23, 42, 0.08)',
        soft: '0 1px 3px rgba(15, 23, 42, 0.05)',
      },
    },
  },
  plugins: [],
} satisfies Config;
