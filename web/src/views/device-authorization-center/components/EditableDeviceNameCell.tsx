import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { Button, Input, Space, Typography } from 'antd';
import type { DeviceAuthorizationRequestRecord } from '../../../api/modules/devices';

type EditableDeviceNameCellProps = {
  record: DeviceAuthorizationRequestRecord;
  editingDeviceCode: string | null;
  editingDeviceName: string;
  saving: boolean;
  onOpenEdit: (record: DeviceAuthorizationRequestRecord) => void;
  onNameChange: (value: string) => void;
  onSave: (record: DeviceAuthorizationRequestRecord) => void;
  onCancel: () => void;
};

export const EditableDeviceNameCell = ({
  record,
  editingDeviceCode,
  editingDeviceName,
  saving,
  onOpenEdit,
  onNameChange,
  onSave,
  onCancel,
}: EditableDeviceNameCellProps) => {
  if (editingDeviceCode !== record.deviceCode) {
    return (
      <Typography.Text className="cursor-text" onDoubleClick={() => onOpenEdit(record)}>
        {record.name || '-'}
      </Typography.Text>
    );
  }

  return (
    <Space.Compact className="w-full">
      <Input
        autoFocus
        size="small"
        value={editingDeviceName}
        onChange={(event) => onNameChange(event.target.value)}
        onPressEnter={() => onSave(record)}
      />
      <Button size="small" type="primary" icon={<CheckOutlined />} loading={saving} onClick={() => onSave(record)} />
      <Button size="small" icon={<CloseOutlined />} disabled={saving} onClick={onCancel} />
    </Space.Compact>
  );
};
