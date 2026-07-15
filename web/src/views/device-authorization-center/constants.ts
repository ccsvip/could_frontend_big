import type { DeviceActivationLogRecord, DeviceAuthorizationRequestRecord } from '../../api/modules/devices';

export const PAGE_SIZE = 10;

export const bindingStatusMap: Record<DeviceAuthorizationRequestRecord['bindingStatus'], { color: string; text: string }> = {
  pending: { color: 'warning', text: '待绑定公司' },
  bound: { color: 'success', text: '已绑定公司' },
  ignored: { color: 'default', text: '已忽略' },
};

export const runtimeStatusMap: Record<DeviceAuthorizationRequestRecord['runtimeStatus'], { color: string; text: string }> = {
  waiting_application: { color: 'default', text: '待绑定智能体' },
  waiting_agent: { color: 'default', text: '待绑定智能体' },
  ready: { color: 'processing', text: '可拉取配置' },
};

export const logActionMap: Record<DeviceActivationLogRecord['action'], { color: string; text: string }> = {
  activate: { color: 'processing', text: '请求授权' },
  bind: { color: 'success', text: '绑定' },
  ignore: { color: 'default', text: '忽略' },
  authorize: { color: 'geekblue', text: '再次授权' },
  revoke: { color: 'error', text: '停用设备' },
};
