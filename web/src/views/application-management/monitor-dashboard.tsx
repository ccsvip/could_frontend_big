import { useMemo, type ReactNode } from 'react';
import { Card, Empty, Progress, Spin, Tag, theme } from 'antd';
import {
  IconChartBar,
  IconChevronDown,
  IconChevronUp,
  IconDatabase,
  IconMessage,
  IconRobot,
  IconUser,
} from '@tabler/icons-react';
import dayjs from 'dayjs';
import type {
  AgentAnnotationRecord,
  AgentApplicationRecord,
  AgentApplicationStats,
} from '../../api/modules/applications';

type ApplicationMonitorDashboardProps = {
  selectedApplication: AgentApplicationRecord | null;
  stats: AgentApplicationStats | null;
  statsLoading: boolean;
  annotations: AgentAnnotationRecord[];
  annotationsLoading: boolean;
};

type MonitorViewModel = {
  totalFeedback: number;
  positiveRate: number | null;
  annotationHitCount: number;
  generatedReplyCount: number;
  topQuestions: { key: string; question: string; count: number; activeRate: number; score: string }[];
  replySources: { label: string; value: number; color: string }[];
  messageRows: { label: string; value: number; icon: ReactNode }[];
  maxTrendCount: number;
};

const formatNumber = (value: number) => new Intl.NumberFormat('zh-CN').format(value);

const formatPercent = (value: number | null) => (value === null ? '--' : `${value}%`);

const clampPercent = (value: number) => Math.max(0, Math.min(100, value));

const buildMonitorViewModel = (
  stats: AgentApplicationStats,
  annotations: AgentAnnotationRecord[],
  primaryColor: string,
  successColor: string,
  warningColor: string,
): MonitorViewModel => {
  const totalFeedback = stats.upCount + stats.downCount;
  const positiveRate = totalFeedback > 0 ? Math.round((stats.upCount / totalFeedback) * 100) : null;
  const annotationHitCount = annotations.reduce((sum, item) => sum + item.hitCount, 0);
  const generatedReplyCount = Math.max(
    stats.assistantMessageCount - Math.min(annotationHitCount, stats.assistantMessageCount),
    0,
  );
  const maxTrendCount = Math.max(...stats.dailyTrends.map((item) => item.count), 1);

  return {
    totalFeedback,
    positiveRate,
    annotationHitCount,
    generatedReplyCount,
    topQuestions: annotations
      .slice()
      .sort((a, b) => b.hitCount - a.hitCount)
      .slice(0, 10)
      .map((item) => ({
        key: `annotation-${item.id}`,
        question: item.question,
        count: item.hitCount,
        activeRate: item.isActive ? 100 : 0,
        score: item.isActive ? '启用' : '停用',
      })),
    replySources: [
      { label: '标注命中回复', value: annotationHitCount, color: successColor },
      { label: '模型/机器人生成', value: generatedReplyCount, color: primaryColor },
      { label: '点踩反馈样本', value: stats.downCount, color: warningColor },
    ].filter((item) => item.value > 0),
    messageRows: [
      { label: '用户消息', value: stats.userMessageCount, icon: <IconUser size={18} /> },
      { label: '助手消息', value: stats.assistantMessageCount, icon: <IconRobot size={18} /> },
      { label: '网页/设备会话', value: stats.conversationCount, icon: <IconMessage size={18} /> },
      { label: '标注命中', value: annotationHitCount, icon: <IconDatabase size={18} /> },
    ],
    maxTrendCount,
  };
};

const MetricCard = ({
  label,
  value,
  helper,
  icon,
}: {
  label: string;
  value: string;
  helper: string;
  icon: ReactNode;
}) => (
  <Card variant="borderless" className="rounded-xl border border-slate-200/70 bg-white shadow-card">
    <div className="flex min-h-24 items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-fluid-sm text-slate-500">{label}</div>
        <div className="mt-3 text-fluid-stat font-bold leading-none text-slate-900">{value}</div>
        <div className="mt-3 text-fluid-xs text-slate-400">{helper}</div>
      </div>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
        {icon}
      </span>
    </div>
  </Card>
);

const TrendLine = ({
  dailyTrends,
  maxCount,
  stroke,
}: {
  dailyTrends: AgentApplicationStats['dailyTrends'];
  maxCount: number;
  stroke: string;
}) => {
  const width = 720;
  const height = 260;
  const paddingX = 26;
  const paddingY = 28;
  const innerWidth = width - paddingX * 2;
  const innerHeight = height - paddingY * 2;
  const points = dailyTrends.map((item, index) => {
    const x = paddingX + (dailyTrends.length <= 1 ? innerWidth : (index / (dailyTrends.length - 1)) * innerWidth);
    const y = paddingY + innerHeight - (item.count / maxCount) * innerHeight;
    return { x, y, ...item };
  });
  const pointList = points.map((point) => `${point.x},${point.y}`).join(' ');
  const areaPath = points.length
    ? `M ${points[0].x} ${height - paddingY} L ${points.map((point) => `${point.x} ${point.y}`).join(' L ')} L ${points[points.length - 1].x} ${height - paddingY} Z`
    : '';

  return (
    <div className="h-full min-h-72 w-full">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
        {[0, 1, 2, 3].map((line) => {
          const y = paddingY + (line / 3) * innerHeight;
          return <line key={line} x1={paddingX} x2={width - paddingX} y1={y} y2={y} stroke="rgb(226 232 240)" strokeDasharray="6 8" />;
        })}
        {areaPath ? <path d={areaPath} fill={stroke} opacity="0.12" /> : null}
        {points.length ? <polyline points={pointList} fill="none" stroke={stroke} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /> : null}
        {points.map((point) => (
          <g key={point.date}>
            <circle cx={point.x} cy={point.y} r="5" fill={stroke} />
            <text x={point.x} y={height - 6} textAnchor="middle" className="fill-slate-500 text-fluid-xs">
              {dayjs(point.date).format('MM/DD')}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
};

const ReplyDonut = ({ sources }: { sources: MonitorViewModel['replySources'] }) => {
  const total = sources.reduce((sum, item) => sum + item.value, 0);
  let cursor = 0;
  const gradient = total > 0
    ? sources
        .map((item) => {
          const start = cursor;
          const end = cursor + (item.value / total) * 100;
          cursor = end;
          return `${item.color} ${start}% ${end}%`;
        })
        .join(', ')
    : 'rgb(226 232 240) 0% 100%';

  return (
    <div className="flex flex-col items-center gap-6 lg:flex-row lg:items-center">
      <div
        className="relative grid aspect-square w-full max-w-52 place-items-center rounded-full"
        style={{ background: `conic-gradient(${gradient})` }}
      >
        <div className="grid h-[58%] w-[58%] place-items-center rounded-full bg-white text-center shadow-sm">
          <div>
            <div className="text-fluid-xs text-slate-500">总回复</div>
            <div className="text-fluid-xl font-bold text-slate-900">{formatNumber(total)}</div>
          </div>
        </div>
      </div>
      <div className="flex w-full flex-1 flex-col gap-3">
        {sources.length > 0 ? sources.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="truncate text-fluid-sm text-slate-600">{item.label}</span>
            </div>
            <span className="shrink-0 text-fluid-sm font-semibold text-slate-900">
              {formatNumber(item.value)}
            </span>
          </div>
        )) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无回复来源数据" />
        )}
      </div>
    </div>
  );
};

const QuestionTable = ({ questions }: { questions: MonitorViewModel['topQuestions'] }) => (
  <Card variant="borderless" className="rounded-xl border border-slate-200/70 bg-white shadow-card">
    <div className="mb-4">
      <div className="text-fluid-lg text-slate-900">热门问题 Top 10</div>
      <div className="text-fluid-sm text-slate-500">按标注命中次数排序</div>
    </div>
    {questions.length > 0 ? (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse">
          <thead>
            <tr className="border-b border-slate-100 text-left text-fluid-sm text-slate-500">
              <th className="w-12 py-3 font-medium">#</th>
              <th className="py-3 font-medium">问题</th>
              <th className="w-28 py-3 text-right font-medium">命中次数</th>
              <th className="w-36 py-3 text-right font-medium">启用状态</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((item, index) => (
              <tr key={item.key} className="border-b border-slate-100 last:border-b-0">
                <td className="py-3 text-fluid-sm text-slate-500">{index + 1}</td>
                <td className="max-w-0 py-3 text-fluid-base text-slate-900">
                  <span className="line-clamp-1">{item.question}</span>
                </td>
                <td className="py-3 text-right text-fluid-base font-semibold text-slate-900">{formatNumber(item.count)}</td>
                <td className="py-3 text-right">
                  <Progress percent={item.activeRate} showInfo={false} size="small" />
                  <span className="text-fluid-xs text-slate-500">{item.score}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标注命中问题" />
    )}
  </Card>
);

export const ApplicationMonitorDashboard = ({
  selectedApplication,
  stats,
  statsLoading,
  annotations,
  annotationsLoading,
}: ApplicationMonitorDashboardProps) => {
  const { token } = theme.useToken();
  const model = useMemo(
    () => stats ? buildMonitorViewModel(stats, annotations, token.colorPrimary, token.colorSuccess, token.colorWarning) : null,
    [annotations, stats, token.colorPrimary, token.colorSuccess, token.colorWarning],
  );

  if (statsLoading || annotationsLoading) {
    return (
      <Card variant="borderless" className="flex h-full items-center justify-center rounded-xl border border-slate-200/70 bg-white shadow-card">
        <Spin size="large" />
      </Card>
    );
  }

  if (!stats || !model) {
    return (
      <Card variant="borderless" className="flex h-full flex-col items-center justify-center rounded-xl border border-slate-200/70 bg-white text-slate-400 shadow-card" styles={{ body: { alignItems: 'center', display: 'flex', height: '100%', justifyContent: 'center', width: '100%' } }}>
        <Empty description="暂无监测数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto pr-1 custom-scrollbar">
      <div className="flex shrink-0 flex-col gap-3 border-b border-slate-200/70 bg-white px-1 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <IconChartBar size={22} className="text-brand-700" />
            <span className="text-fluid-xl font-bold text-slate-900">监测</span>
            <Tag color={selectedApplication?.isActive ? 'success' : 'default'}>{selectedApplication?.isActive ? '运行中' : '未启用'}</Tag>
          </div>
          <div className="mt-1 text-fluid-sm text-slate-500">
            {selectedApplication?.name || '智能体'} · 样本量、会话趋势、回复来源和标注命中
          </div>
        </div>
        <div className="flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
          <span className="rounded-lg px-3 py-1.5 text-fluid-sm text-slate-500">近 24 小时</span>
          <span className="rounded-lg bg-brand-700 px-3 py-1.5 text-fluid-sm font-semibold text-white">近 7 天</span>
          <span className="rounded-lg px-3 py-1.5 text-fluid-sm text-slate-500">近 30 天</span>
        </div>
      </div>

      <div className="grid shrink-0 grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="总会话数" value={formatNumber(stats.conversationCount)} helper="stats.conversationCount" icon={<IconMessage size={20} />} />
        <MetricCard label="交流消息总量" value={formatNumber(stats.messageCount)} helper={`用户 ${formatNumber(stats.userMessageCount)} / 助手 ${formatNumber(stats.assistantMessageCount)}`} icon={<IconUser size={20} />} />
        <MetricCard label="标注命中" value={formatNumber(model.annotationHitCount)} helper="来自应用标注 hitCount" icon={<IconDatabase size={20} />} />
        <MetricCard label="好评率" value={formatPercent(model.positiveRate)} helper={`点赞 ${formatNumber(stats.upCount)} / 点踩 ${formatNumber(stats.downCount)}`} icon={<IconChevronUp size={20} />} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,_2fr)_minmax(320px,_1fr)]">
        <Card variant="borderless" className="min-h-[360px] rounded-xl border border-slate-200/70 bg-white shadow-card" styles={{ body: { height: '100%', padding: 20 } }}>
          <div className="mb-3">
            <div className="text-fluid-lg text-slate-900">会话量趋势</div>
            <div className="text-fluid-sm text-slate-500">按 stats.dailyTrends 绘制</div>
          </div>
          <TrendLine dailyTrends={stats.dailyTrends} maxCount={model.maxTrendCount} stroke={token.colorPrimary} />
        </Card>
        <Card variant="borderless" className="rounded-xl border border-slate-200/70 bg-white shadow-card" styles={{ body: { padding: 20 } }}>
          <div className="mb-5">
            <div className="text-fluid-lg text-slate-900">回复来源</div>
            <div className="text-fluid-sm text-slate-500">标注命中与助手回复构成</div>
          </div>
          <ReplyDonut sources={model.replySources} />
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,_2fr)_minmax(320px,_1fr)]">
        <Card variant="borderless" className="rounded-xl border border-slate-200/70 bg-white shadow-card">
          <div className="mb-5">
            <div className="text-fluid-lg text-slate-900">消息构成</div>
            <div className="text-fluid-sm text-slate-500">按现有统计字段拆分</div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {model.messageRows.map((row) => (
              <div key={row.label} className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-brand-700">{row.icon}</span>
                  <span className="text-fluid-xl font-bold text-slate-900">{formatNumber(row.value)}</span>
                </div>
                <div className="mt-3 text-fluid-sm text-slate-500">{row.label}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card variant="borderless" className="rounded-xl border border-slate-200/70 bg-white shadow-card">
          <div className="mb-5">
            <div className="text-fluid-lg text-slate-900">响应反馈分布</div>
            <div className="text-fluid-sm text-slate-500">点赞 / 点踩样本</div>
          </div>
          <div className="flex flex-col gap-5">
            <Progress percent={clampPercent(model.positiveRate || 0)} strokeColor={token.colorSuccess} trailColor="rgb(241 245 249)" />
            <div className="flex items-center justify-between text-fluid-sm">
              <span className="flex items-center gap-2 text-emerald-600"><IconChevronUp size={16} />{formatNumber(stats.upCount)}</span>
              <span className="flex items-center gap-2 text-rose-600"><IconChevronDown size={16} />{formatNumber(stats.downCount)}</span>
            </div>
          </div>
        </Card>
      </div>

      <QuestionTable questions={model.topQuestions} />
    </div>
  );
};
