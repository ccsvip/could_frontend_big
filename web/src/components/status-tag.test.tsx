import { StatusTag, StatusType } from './status-tag';

/**
 * Unit verification for StatusTag interface and component behavior
 */
export function testStatusTagInterface() {
  const validTypes: StatusType[] = [
    'online',
    'offline',
    'active',
    'inactive',
    'bound',
    'unbound',
    'pending',
  ];

  const elements = validTypes.map((type) => (
    <StatusTag key={type} type={type} />
  ));

  const customTag = <StatusTag type="online" label="自定义在线" />;

  return { elements, customTag };
}
