import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { Card, Empty, Progress, Segmented, Spin, Tag, theme } from 'antd';
import {
  IconChartBar,
  IconChevronDown,
  IconChevronUp,
  IconDatabase,
  IconMessage,
  IconUser,
} from '@tabler/icons-react';
import * as echarts from 'echarts';
import dayjs from 'dayjs';
import type {
  AgentAnnotationRecord,
  AgentApplicationRecord,
  AgentApplicationStats,
  AgentApplicationStatsRange,
} from '../../api/modules/applications';

type ApplicationMonitorDashboardProps = {
  selectedApplication: AgentApplicationRecord | null;
  stats: AgentApplicationStats | null;
  statsLoading: boolean;
  statsRange: AgentApplicationStatsRange;
  onStatsRangeChange: (range: AgentApplicationStatsRange) => void;
  annotations: AgentAnnotationRecord[];
  annotationsLoading: boolean;
};

const fmt = (value: number) => new Intl.NumberFormat('zh-CN').format(value);
const fmtPct = (value: number | null) => (value === null ? '--' : `${value}%`);

const STATS_RANGE_OPTIONS: { label: string; value: AgentApplicationStatsRange }[] = [
  { label: '近 24 小时', value: '24h' },
  { label: '近 7 天', value: '7d' },
  { label: '近 30 天', value: '30d' },
];

const STATS_RANGE_TREND_LABEL: Record<AgentApplicationStatsRange, string> = {
  '24h': '近 24 小时每小时会话数变化',
  '7d': '近 7 天每日会话数变化',
  '30d': '近 30 天每日会话数变化',
};

// ============================================================
// ECharts trend chart
// ============================================================

const TrendChart = ({
  dailyTrends,
  color,
  statsRange,
}: {
  dailyTrends: { date: string; count: number }[];
  color: string;
  statsRange: AgentApplicationStatsRange;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const hasTrendData = dailyTrends.length > 0;

  useEffect(() => {
    if (!hasTrendData || !containerRef.current) return;

    const chart = echarts.getInstanceByDom(containerRef.current) ?? echarts.init(containerRef.current);
    chartRef.current = chart;

    const categories = dailyTrends.map((d) => (
      statsRange === '24h' ? dayjs(d.date).format('HH:mm') : dayjs(d.date).format('MM/DD')
    ));
    const values = dailyTrends.map((d) => d.count);
    const maxVal = Math.max(...values, 1);

    chart.setOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#fff',
        borderColor: 'rgb(226 232 240)',
        textStyle: { color: '#334155', fontSize: 13 },
        formatter: (params: { data: number; axisValueLabel: string }[]) =>
          `${params[0]?.axisValueLabel || ''}<br/><strong>${params[0]?.data ?? 0}</strong> 次会话`,
      },
      grid: { top: 12, right: 16, bottom: 24, left: 40 },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: 'rgb(226 232 240)' } },
        axisTick: { show: false },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: maxVal < 4 ? 4 : undefined,
        minInterval: 1,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: 'rgb(241 245 249)', type: 'dashed' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          data: values,
          barWidth: '50%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color },
              { offset: 1, color: color + '66' },
            ]),
            borderRadius: [6, 6, 0, 0],
          },
          emphasis: {
            itemStyle: { color },
          },
        },
        {
          type: 'line',
          data: values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { color, width: 2 },
          itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: color + '22' },
              { offset: 1, color: color + '04' },
            ]),
          },
        },
      ],
    });

    const handleResize = () => chart.resize();
    const resizeFrame = window.requestAnimationFrame(handleResize);
    window.addEventListener('resize', handleResize);
    return () => {
      window.cancelAnimationFrame(resizeFrame);
      window.removeEventListener('resize', handleResize);
      chart.dispose();
      if (chartRef.current === chart) {
        chartRef.current = null;
      }
    };
  }, [dailyTrends, color, hasTrendData, statsRange]);

  if (!hasTrendData) {
    return (
      <div className="flex h-full min-h-[260px] items-center justify-center">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势数据" />
      </div>
    );
  }

  return <div ref={containerRef} className="h-full min-h-[260px] w-full" />;
};

// ============================================================
// Sub-components
// ============================================================

const AccentCard = ({
  label,
  value,
  icon,
  accent,
  bg,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  accent: string;
  bg: string;
}) => (
  <Card variant="borderless" className="overflow-hidden rounded-xl border border-slate-200/70 shadow-card" styles={{ body: { padding: 0 } }}>
    <div className="h-1" style={{ backgroundColor: accent }} />
    <div className="flex items-start justify-between gap-3 p-4">
      <div className="min-w-0">
        <div className="text-fluid-xs text-slate-500">{label}</div>
        <div className="mt-1 text-fluid-stat font-bold text-slate-900">{value}</div>
      </div>
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${bg}`} style={{ color: accent }}>
        {icon}
      </span>
    </div>
  </Card>
);

const SourceBadge = ({ label, value, color }: { label: string; value: number; color: string }) => (
  <div className="flex min-w-[120px] flex-1 flex-col gap-2 rounded-xl border border-slate-100 bg-slate-50/70 p-4">
    <span className="h-1 w-8 rounded-full" style={{ backgroundColor: color }} />
    <span className="text-fluid-xl font-bold text-slate-900">{fmt(value)}</span>
    <span className="text-fluid-xs text-slate-500">{label}</span>
  </div>
);

const QuestionCard = ({ annotations }: { annotations: AgentAnnotationRecord[] }) => {
  const sorted = useMemo(
    () => annotations.slice().sort((a, b) => b.hitCount - a.hitCount).slice(0, 10),
    [annotations],
  );

  if (sorted.length === 0) {
    return (
      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标注命中问题" />
      </Card>
    );
  }

  return (
    <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card" styles={{ body: { padding: 24 } }}>
      <div className="mb-4">
        <div className="text-fluid-lg text-slate-900">热门问题 Top 10</div>
        <div className="text-fluid-xs text-slate-400">按标注命中次数排序</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[540px] border-collapse">
          <thead>
            <tr className="border-b border-slate-100 text-left text-fluid-xs uppercase tracking-wide text-slate-400">
              <th className="w-10 py-3 font-medium">#</th>
              <th className="py-3 font-medium">问题</th>
              <th className="w-24 py-3 text-right font-medium">命中次数</th>
              <th className="w-20 py-3 text-right font-medium">状态</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((q, i) => (
              <tr key={q.id} className="border-b border-slate-50 transition hover:bg-slate-50/50">
                <td className="py-3 text-fluid-sm text-slate-400">{i + 1}</td>
                <td className="max-w-0 py-3 text-fluid-base text-slate-900">
                  <span className="line-clamp-1">{q.question}</span>
                </td>
                <td className="py-3 text-right text-fluid-sm font-semibold text-slate-900">{fmt(q.hitCount)}</td>
                <td className="py-3 text-right">
                  <Tag color={q.isActive ? 'success' : 'default'}>{q.isActive ? '启用' : '停用'}</Tag>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

// ============================================================
// Main component
// ============================================================

export const ApplicationMonitorDashboard = ({
  selectedApplication,
  stats,
  statsLoading,
  statsRange,
  onStatsRangeChange,
  annotations,
  annotationsLoading,
}: ApplicationMonitorDashboardProps) => {
  const { token } = theme.useToken();

  if (statsLoading || annotationsLoading) {
    return (
      <Card variant="borderless" className="flex h-full items-center justify-center rounded-xl border border-slate-200/70 shadow-card">
        <Spin size="large" />
      </Card>
    );
  }

  if (!stats) {
    return (
      <Card variant="borderless" className="flex h-full flex-col items-center justify-center rounded-xl border border-slate-200/70 shadow-card" styles={{ body: { alignItems: 'center', display: 'flex', height: '100%', justifyContent: 'center', width: '100%' } }}>
        <Empty description="暂无监测数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const totalFeedback = stats.upCount + stats.downCount;
  const positiveRate = totalFeedback > 0 ? Math.round((stats.upCount / totalFeedback) * 100) : null;
  const hitCount = annotations.reduce((s, a) => s + a.hitCount, 0);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto pr-1 custom-scrollbar">
      {/* Header */}
      <div className="flex shrink-0 flex-col gap-3 border-b border-slate-200/70 bg-white px-1 pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <IconChartBar size={22} className="text-brand-700" />
            <span className="text-fluid-xl font-bold text-slate-900">监测</span>
            <Tag color={selectedApplication?.isActive ? 'success' : 'default'}>{selectedApplication?.isActive ? '运行中' : '未启用'}</Tag>
          </div>
          <div className="mt-1 text-fluid-sm text-slate-500">
            {selectedApplication?.name || '智能体'} · 会话趋势、回复来源与标注命中
          </div>
        </div>
        <Segmented
          value={statsRange}
          options={STATS_RANGE_OPTIONS}
          onChange={(value) => onStatsRangeChange(value as AgentApplicationStatsRange)}
        />
      </div>

      {/* Metric cards — accent bar style */}
      <div className="grid shrink-0 grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AccentCard label="总会话数" value={fmt(stats.conversationCount)} icon={<IconMessage size={22} />} accent={token.colorPrimary} bg="bg-brand-50" />
        <AccentCard label="用户消息" value={fmt(stats.userMessageCount)} icon={<IconUser size={22} />} accent="#6366f1" bg="bg-indigo-50" />
        <AccentCard label="累计标注命中" value={fmt(hitCount)} icon={<IconDatabase size={22} />} accent={token.colorSuccess} bg="bg-emerald-50" />
        <AccentCard label="好评率" value={fmtPct(positiveRate)} icon={positiveRate && positiveRate >= 50 ? <IconChevronUp size={22} /> : <IconChevronDown size={22} />} accent={token.colorWarning} bg="bg-amber-50" />
      </div>

      {/* ECharts trend + Reply source */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,_2fr)_minmax(320px,_1fr)]">
        <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card" styles={{ body: { padding: 20 } }}>
          <div className="mb-2 flex items-center justify-between">
            <div>
              <div className="text-fluid-lg text-slate-900">会话量趋势</div>
              <div className="text-fluid-xs text-slate-400">{STATS_RANGE_TREND_LABEL[statsRange]}</div>
            </div>
          </div>
          <TrendChart dailyTrends={stats.dailyTrends} color={token.colorPrimary} statsRange={statsRange} />
        </Card>
        <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card" styles={{ body: { padding: 24 } }}>
          <div className="mb-5">
            <div className="text-fluid-lg text-slate-900">回复来源构成</div>
            <div className="text-fluid-sm text-slate-500">标注命中与模型生成占比</div>
          </div>
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-3">
              {[
                { label: '标注命中', val: hitCount, color: token.colorSuccess },
                { label: '模型生成', val: Math.max(stats.assistantMessageCount - hitCount, 0), color: token.colorPrimary },
                { label: '点踩样本', val: stats.downCount, color: token.colorWarning },
              ].filter((s) => s.val > 0).map((s) => (
                <SourceBadge key={s.label} label={s.label} value={s.val} color={s.color} />
              ))}
            </div>
            {/* Feedback distribution inline */}
            <div className="mt-2 rounded-xl bg-slate-50 p-4">
              <div className="mb-3 text-fluid-xs font-medium text-slate-500">反馈分布</div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 shrink-0">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
                    <IconChevronUp size={20} className="text-emerald-600" />
                  </span>
                  <span className="text-fluid-sm font-bold text-emerald-600">{fmt(stats.upCount)}</span>
                </div>
                <div className="flex-1">
                  <Progress
                    percent={positiveRate || 0}
                    strokeColor={token.colorSuccess}
                    trailColor="rgb(226 232 240)"
                    size={['100%', 10]}
                  />
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-50">
                    <IconChevronDown size={20} className="text-rose-600" />
                  </span>
                  <span className="text-fluid-sm font-bold text-rose-600">{fmt(stats.downCount)}</span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Question table */}
      <QuestionCard annotations={annotations} />
    </div>
  );
};
