import { IconEye, IconFileUnknown, IconReload, IconSearch } from '@tabler/icons-react';
import { Button, Card, Descriptions, Drawer, Input, Select, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchErrorCodes,
  type ErrorCodeRecord,
} from '../../api/modules/error-codes';


export const ErrorCodeCenterPage = () => {
  const [records, setRecords] = useState<ErrorCodeRecord[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [keywordInput, setKeywordInput] = useState('');
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [usesServerPagination, setUsesServerPagination] = useState(false);
  const [activeRecord, setActiveRecord] = useState<ErrorCodeRecord | null>(null);

  const loadErrorCodes = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchErrorCodes({ keyword, category, page });
      const nextRecords = Array.isArray(response) ? response : response.results;
      setRecords(nextRecords);
      setTotal(Array.isArray(response) ? response.length : response.count);
      setUsesServerPagination(!Array.isArray(response));
      const catalogueCategories = Array.isArray(response) ? [] : response.categories ?? [];
      setCategories(catalogueCategories.length > 0
        ? catalogueCategories
        : (previous) => Array.from(new Set([...previous, ...nextRecords.map((record) => record.category)])).sort());
    } catch {
      message.error('错误码目录加载失败');
    } finally {
      setLoading(false);
    }
  }, [category, keyword, page]);

  useEffect(() => {
    void loadErrorCodes();
  }, [loadErrorCodes]);

  const applyKeyword = () => {
    setPage(1);
    setKeyword(keywordInput.trim());
  };

  const resetFilters = () => {
    setKeywordInput('');
    setKeyword('');
    setCategory(undefined);
    setPage(1);
  };

  const categoryOptions = useMemo(
    () => categories.map((value) => ({ label: value, value })),
    [categories],
  );

  const columns: ColumnsType<ErrorCodeRecord> = [
    {
      title: '错误码',
      dataIndex: 'code',
      key: 'code',
      width: 220,
      render: (value: string) => <span className="font-mono text-fluid-sm font-semibold text-slate-800">{value}</span>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 160,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '默认提示',
      dataIndex: 'defaultMessage',
      key: 'defaultMessage',
      width: 240,
      ellipsis: true,
      render: (value: string) => <span className="text-fluid-sm text-slate-700">{value}</span>,
    },
    {
      title: '适用通道',
      dataIndex: 'transports',
      key: 'transports',
      width: 160,
      render: (value: string[]) => value.map((transport) => <Tag key={transport}>{transport}</Tag>),
    },
    {
      title: '查看',
      key: 'actions',
      fixed: 'right',
      width: 96,
      render: (_, record) => (
        <Button type="link" icon={<IconEye size={16} />} onClick={() => setActiveRecord(record)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div className="container space-y-5 py-4 sm:py-6">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700 shadow-sm">
              <IconFileUnknown size={24} />
            </div>
            <div className="min-w-0">
              <div className="mb-1 text-fluid-xs font-semibold uppercase tracking-[0.14em] text-brand-700">Platform reference</div>
              <h1 className="text-fluid-xl text-slate-900">错误码中心</h1>
              <p className="mt-1 text-fluid-base text-slate-500">查看实时服务错误码的含义、影响范围及推荐处理方式。</p>
            </div>
          </div>
          <Button icon={<IconReload size={16} />} onClick={() => void loadErrorCodes()}>
            刷新目录
          </Button>
        </div>
      </div>

      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <Input
            allowClear
            className="w-full lg:max-w-md"
            placeholder="搜索错误码、默认提示或说明"
            prefix={<IconSearch size={16} className="text-slate-400" />}
            value={keywordInput}
            onChange={(event) => setKeywordInput(event.target.value)}
            onPressEnter={applyKeyword}
          />
          <Select
            allowClear
            className="w-full lg:w-56"
            options={categoryOptions}
            placeholder="按分类筛选"
            value={category}
            onChange={(value: string | undefined) => {
              setCategory(value);
              setPage(1);
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="primary" icon={<IconSearch size={16} />} onClick={applyKeyword}>
              搜索
            </Button>
            <Button onClick={resetFilters}>重置</Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" className="rounded-xl border border-slate-200/70 shadow-card">
        <Table
          columns={columns}
          dataSource={records}
          loading={loading}
          locale={{ emptyText: '暂无匹配的错误码' }}
          pagination={usesServerPagination
            ? {
                current: page,
                total,
                showSizeChanger: false,
                onChange: (nextPage) => setPage(nextPage),
              }
            : { pageSize: 10, showSizeChanger: false }}
          rowKey="code"
          scroll={{ x: 1080 }}
        />
      </Card>

      <Drawer
        destroyOnHidden
        open={Boolean(activeRecord)}
        onClose={() => setActiveRecord(null)}
        title={activeRecord ? `错误码详情 · ${activeRecord.code}` : '错误码详情'}
        width="min(560px, 100vw)"
      >
        {activeRecord ? (
          <Descriptions bordered column={1} size="middle">
            <Descriptions.Item label="错误码">
              <span className="font-mono text-fluid-sm font-semibold text-slate-800">{activeRecord.code}</span>
            </Descriptions.Item>
            <Descriptions.Item label="分类"><Tag>{activeRecord.category}</Tag></Descriptions.Item>
            <Descriptions.Item label="默认提示">{activeRecord.defaultMessage}</Descriptions.Item>
            <Descriptions.Item label="说明">
              <Typography.Paragraph className="mb-0 whitespace-pre-wrap text-fluid-base text-slate-700">
                {activeRecord.description}
              </Typography.Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="推荐处理方式">
              <Typography.Paragraph className="mb-0 whitespace-pre-wrap text-fluid-base text-slate-700">
                {activeRecord.recommendedAction}
              </Typography.Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="适用通道">
              {activeRecord.transports.map((transport) => <Tag key={transport}>{transport}</Tag>)}
            </Descriptions.Item>
          </Descriptions>
        ) : null}
      </Drawer>
    </div>
  );
};
