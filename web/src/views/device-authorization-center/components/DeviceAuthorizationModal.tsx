import { DatePicker, Form, Modal, Select, Switch } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import type { DeviceAuthorizationRequestRecord } from '../../../api/modules/devices';
import type { BindForm, BindMode, SelectOption } from '../types';

type DeviceAuthorizationModalProps = {
  request: DeviceAuthorizationRequestRecord | null;
  mode: BindMode;
  form: FormInstance<BindForm>;
  tenantOptions: SelectOption<number>[];
  applicationOptions: SelectOption<number | null>[];
  agentApplicationOptions: SelectOption<number | null>[];
  groupOptions: SelectOption<number | null>[];
  saving: boolean;
  onCancel: () => void;
  onSave: () => void;
  onTenantChange: (tenantId: number) => void;
};

export const DeviceAuthorizationModal = ({
  request,
  mode,
  form,
  tenantOptions,
  applicationOptions,
  agentApplicationOptions,
  groupOptions,
  saving,
  onCancel,
  onSave,
  onTenantChange,
}: DeviceAuthorizationModalProps) => {
  const actionText = mode === 'bind' ? '绑定设备' : '再次授权';

  return (
    <Modal
      title={request ? `${actionText} ${request.deviceCode}` : actionText}
      open={Boolean(request)}
      onCancel={onCancel}
      onOk={onSave}
      okText={mode === 'bind' ? '保存绑定' : '保存授权'}
      cancelText="取消"
      confirmLoading={saving}
      destroyOnHidden
    >
      <Form<BindForm> form={form} layout="vertical">
        <Form.Item label="所属公司" name="tenantId" rules={[{ required: true, message: '请选择公司' }]}>
          <Select options={tenantOptions} onChange={onTenantChange} />
        </Form.Item>
        <Form.Item label="绑定智能体" name="agentApplicationId" rules={[{ required: true, message: '请选择智能体' }]}>
          <Select options={agentApplicationOptions} optionFilterProp="label" showSearch />
        </Form.Item>
        <Form.Item label="资源应用" name="applicationId">
          <Select options={applicationOptions} optionFilterProp="label" showSearch />
        </Form.Item>
        <Form.Item label="设备分组" name="groupId">
          <Select options={groupOptions} optionFilterProp="label" showSearch />
        </Form.Item>
        <Form.Item label="授权类型" name="authorizationType" rules={[{ required: true, message: '请选择授权类型' }]}>
          <Select
            options={[
              { label: '永久', value: 'permanent' },
              { label: '试用', value: 'trial' },
            ]}
          />
        </Form.Item>
        <Form.Item dependencies={['authorizationType']} noStyle>
          {({ getFieldValue }) =>
            getFieldValue('authorizationType') === 'trial' ? (
              <Form.Item label="到期时间" name="expiresAt" rules={[{ required: true, message: '请选择到期时间' }]}>
                <DatePicker
                  className="w-full"
                  format="YYYY-MM-DD HH:mm:ss"
                  placeholder="请选择到期时间"
                  showNow={false}
                  showTime={{ defaultValue: dayjs('23:59:59', 'HH:mm:ss') }}
                />
              </Form.Item>
            ) : null
          }
        </Form.Item>
        <Form.Item label="启用设备" name="isEnabled" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
};
