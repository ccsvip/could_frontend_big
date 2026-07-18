import { IconDeviceFloppy, IconReload } from '@tabler/icons-react';
import { Button, Input, InputNumber, message, Popconfirm, Tag, Typography } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchControlCommandRecognitionPolicy,
  restoreControlCommandRecognitionPolicyDefaults,
  updateControlCommandRecognitionPolicy,
} from '../../api/modules/commands';

type ControlCommandRecognitionPolicyPanelProps = {
  canUpdate: boolean;
};

const DEFAULT_DIRECT_THRESHOLD = 0.9;
const DEFAULT_CONFIRMATION_THRESHOLD = 0.7;

const toThreshold = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const ControlCommandRecognitionPolicyPanel = ({ canUpdate }: ControlCommandRecognitionPolicyPanelProps) => {
  const [fixedExecutionReply, setFixedExecutionReply] = useState('');
  const [effectiveDirectThreshold, setEffectiveDirectThreshold] = useState(DEFAULT_DIRECT_THRESHOLD);
  const [effectiveConfirmationThreshold, setEffectiveConfirmationThreshold] = useState(DEFAULT_CONFIRMATION_THRESHOLD);
  const [directThreshold, setDirectThreshold] = useState(DEFAULT_DIRECT_THRESHOLD);
  const [confirmationThreshold, setConfirmationThreshold] = useState(DEFAULT_CONFIRMATION_THRESHOLD);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingFixedReply, setSavingFixedReply] = useState(false);

  const loadPolicy = useCallback(async () => {
    setLoading(true);
    try {
      const policy = await fetchControlCommandRecognitionPolicy();
      const direct = toThreshold(policy.directExecutionThreshold, DEFAULT_DIRECT_THRESHOLD);
      const confirmation = toThreshold(policy.llmConfirmationThreshold, DEFAULT_CONFIRMATION_THRESHOLD);
      setFixedExecutionReply(policy.fixedExecutionReply || '');
      setEffectiveDirectThreshold(direct);
      setEffectiveConfirmationThreshold(confirmation);
      setDirectThreshold(direct);
      setConfirmationThreshold(confirmation);
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPolicy();
  }, [loadPolicy]);

  const validationMessage = useMemo(() => {
    if (directThreshold < 0.9 || directThreshold > 1) return '直接执行阈值必须在 0.90 到 1.00 之间。';
    if (confirmationThreshold < 0.5 || confirmationThreshold > directThreshold) {
      return 'LLM 确认阈值必须在 0.50 到直接执行阈值之间。';
    }
    return '';
  }, [confirmationThreshold, directThreshold]);

  const saveFixedReply = async () => {
    const value = fixedExecutionReply.trim();
    if (!value) {
      message.error('请输入固定回复');
      return;
    }
    setSavingFixedReply(true);
    try {
      const policy = await updateControlCommandRecognitionPolicy({ fixedExecutionReply: value });
      setFixedExecutionReply(policy.fixedExecutionReply);
      message.success('固定回复已生效');
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setSavingFixedReply(false);
    }
  };

  const savePolicy = async () => {
    if (validationMessage) {
      message.error(validationMessage);
      return;
    }
    setSaving(true);
    try {
      const policy = await updateControlCommandRecognitionPolicy({
        directExecutionThreshold: directThreshold.toFixed(2),
        llmConfirmationThreshold: confirmationThreshold.toFixed(2),
      });
      const direct = toThreshold(policy.directExecutionThreshold, DEFAULT_DIRECT_THRESHOLD);
      const confirmation = toThreshold(policy.llmConfirmationThreshold, DEFAULT_CONFIRMATION_THRESHOLD);
      setEffectiveDirectThreshold(direct);
      setEffectiveConfirmationThreshold(confirmation);
      setDirectThreshold(direct);
      setConfirmationThreshold(confirmation);
      message.success('控制指令识别策略已生效');
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setSaving(false);
    }
  };

  const restoreDefaults = async () => {
    setSaving(true);
    try {
      await restoreControlCommandRecognitionPolicyDefaults();
      await loadPolicy();
      message.success('已恢复默认识别策略');
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border-b border-slate-100 bg-brand-50/50 px-5 py-4">
      <div className="mb-4 flex flex-col gap-2 border-b border-brand-100 pb-4 sm:flex-row sm:items-center">
        <Typography.Text strong className="shrink-0 text-fluid-base text-slate-900">固定回复</Typography.Text>
        <Input
          aria-label="固定回复"
          className="w-full sm:max-w-xl"
          disabled={!canUpdate || loading}
          maxLength={500}
          placeholder="请输入所有控制指令共用的固定回复"
          value={fixedExecutionReply}
          onChange={(event) => setFixedExecutionReply(event.target.value)}
          onPressEnter={() => void saveFixedReply()}
        />
        {canUpdate ? (
          <Button type="primary" loading={savingFixedReply} onClick={() => void saveFixedReply()}>
            确认
          </Button>
        ) : null}
      </div>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Typography.Text strong className="text-fluid-lg text-slate-900">控制指令识别策略</Typography.Text>
            <Tag color="cyan" className="text-fluid-xs">当前生效 {effectiveDirectThreshold.toFixed(2)} / {effectiveConfirmationThreshold.toFixed(2)}</Tag>
          </div>
          <Typography.Text className="text-fluid-sm text-slate-600">
            匹配分数只来自本地指令名称与指令码比较，不包含语音识别或模型置信度。
          </Typography.Text>
        </div>

        <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2 xl:w-auto">
          <label className="flex min-w-0 flex-col gap-1">
            <Typography.Text className="text-fluid-sm text-slate-600">直接执行阈值</Typography.Text>
            <InputNumber
              aria-label="直接执行阈值"
              className="w-full sm:w-40"
              disabled={!canUpdate || loading}
              min={0.9}
              max={1}
              step={0.01}
              precision={2}
              value={directThreshold}
              onChange={(value) => setDirectThreshold(Number(value ?? DEFAULT_DIRECT_THRESHOLD))}
            />
          </label>
          <label className="flex min-w-0 flex-col gap-1">
            <Typography.Text className="text-fluid-sm text-slate-600">LLM 确认阈值</Typography.Text>
            <InputNumber
              aria-label="LLM 确认阈值"
              className="w-full sm:w-40"
              disabled={!canUpdate || loading}
              min={0.5}
              max={directThreshold}
              step={0.01}
              precision={2}
              value={confirmationThreshold}
              onChange={(value) => setConfirmationThreshold(Number(value ?? DEFAULT_CONFIRMATION_THRESHOLD))}
            />
          </label>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 lg:grid-cols-3">
        <div className="border-l-2 border-brand-600 bg-white px-3 py-2 text-fluid-sm text-slate-700">
          直接执行：分数不低于 {directThreshold.toFixed(2)}，且领先下一候选至少 0.10。
        </div>
        <div className="border-l-2 border-cyan-500 bg-white px-3 py-2 text-fluid-sm text-slate-700">
          LLM 确认：分数不低于 {confirmationThreshold.toFixed(2)}，但不满足直接执行条件。
        </div>
        <div className="border-l-2 border-slate-400 bg-white px-3 py-2 text-fluid-sm text-slate-700">
          普通对话：分数低于 {confirmationThreshold.toFixed(2)}，不会触发控制动作。
        </div>
      </div>

      {canUpdate ? (
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <Popconfirm title="确认恢复默认识别策略吗？" onConfirm={() => void restoreDefaults()}>
            <Button icon={<IconReload size={16} />} loading={saving}>恢复默认</Button>
          </Popconfirm>
          <Button type="primary" icon={<IconDeviceFloppy size={16} />} loading={saving} onClick={() => void savePolicy()}>
            保存策略
          </Button>
        </div>
      ) : null}
    </div>
  );
};
