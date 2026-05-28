import { Card, Empty } from 'antd';
import { SoundOutlined } from '@ant-design/icons';

export const TtsManagementPage = () => (
  <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
    <Empty
      image={
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-50 to-teal-100/60 text-teal-700">
          <SoundOutlined style={{ fontSize: 28 }} />
        </div>
      }
      description={
        <span className="text-[14px] font-medium text-slate-500">TTS 管理功能开发中，敬请期待</span>
      }
    />
  </Card>
);
