import { Card, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PAGE_SIZE } from '../constants';

type AuthorizationTableCardProps<T extends object> = {
  columns: ColumnsType<T>;
  dataSource: T[];
  rowKey: string | ((record: T) => string | number);
  loading: boolean;
  scrollX: number;
  currentPage: number;
  total: number;
  emptyText: string;
  onPageChange: (page: number) => void;
};

export const AuthorizationTableCard = <T extends object>({
  columns,
  dataSource,
  rowKey,
  loading,
  scrollX,
  currentPage,
  total,
  emptyText,
  onPageChange,
}: AuthorizationTableCardProps<T>) => (
  <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
    <Table<T>
      columns={columns}
      dataSource={dataSource}
      rowKey={rowKey}
      loading={loading}
      scroll={{ x: scrollX }}
      pagination={{
        current: currentPage,
        pageSize: PAGE_SIZE,
        total,
        showSizeChanger: false,
        onChange: onPageChange,
      }}
      locale={{ emptyText }}
    />
  </Card>
);
