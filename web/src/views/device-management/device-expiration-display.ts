import dayjs from 'dayjs';

type DeviceExpirationInput = {
  authorizationType: 'permanent' | 'trial';
  expiresAt: string | null;
  isSoftwareTrial: boolean;
};

type DeviceExpirationDisplay = {
  softwareExpiration: string;
  modelExpiration: string;
};

export const resolveDeviceExpirationDisplay = ({
  authorizationType,
  expiresAt,
  isSoftwareTrial,
}: DeviceExpirationInput): DeviceExpirationDisplay => {
  const modelExpiration = authorizationType === 'permanent'
    ? '永久'
    : expiresAt
      ? dayjs(expiresAt).format('YYYY-MM-DD')
      : '-';

  return {
    softwareExpiration: authorizationType === 'trial' && isSoftwareTrial ? modelExpiration : '永久',
    modelExpiration,
  };
};
