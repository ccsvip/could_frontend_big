import dayjs from 'dayjs';
import { IconDownload, IconArrowBarToRight, IconReload } from '@tabler/icons-react';
import { Button, Card, Empty, message, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useState } from 'react';
import {
  exportAllCommands,
  fetchCommandGroups,
  type CommandGroupRecord,
} from '../../api/modules/commands';
import {
  buildCommandGroupExportCollectionPayload,
  buildCommandGroupExportFilename,
  buildCommandGroupExportPayload,
} from './command-export-format';
import { collectCommandGroupPages, getCommandGroupExportActionState } from './command-export-state';
import { useAuthStore } from '../../store/auth';

const groupTypeLabels: Record<CommandGroupRecord['groupType'], string> = {
  control: '控制指令',
  task: '任务指令',
};

const downloadJson = (data: unknown, filename: string) => {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
};

const fetchExportManagementGroups = async () => {
  // 导出管理列表展示全部分组；是否允许导出只控制操作按钮可用性。
  return collectCommandGroupPages<CommandGroupRecord>((page) => fetchCommandGroups({ page, isActive: 'all' }));
};

export const CommandExportManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canDownload = hasPermission('commands.export.download');

  const [items, setItems] = useState<CommandGroupRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadingGroupId, setDownloadingGroupId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchExportManagementGroups();
      setItems(response);
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleDownloadCommands = async () => {
    setDownloading(true);
    try {
      const response = await exportAllCommands();
      const exportableGroups = items.filter((item) => item.exportEnabled && item.isActive);
      if (exportableGroups.length === 0) {
        message.warning('暂无允许导出的指令');
        return;
      }

      const payload = buildCommandGroupExportCollectionPayload(exportableGroups, response.controlCommands, response.taskCommands);
      downloadJson(payload, `command-export-collection-${dayjs().format('YYYYMMDDHHmmss')}.json`);
      message.success('已导出指令合集');
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadGroupCommands = async (item: CommandGroupRecord) => {
    setDownloadingGroupId(item.id);
    try {
      const response = await exportAllCommands();
      const payload = buildCommandGroupExportPayload(item, response.controlCommands, response.taskCommands);
      const filename = buildCommandGroupExportFilename(item, dayjs().format('YYYYMMDDHHmmss'));
      downloadJson(payload, filename);
      message.success('已导出指令');
    } catch {
      // 请求错误由全局拦截器统一提示。
    } finally {
      setDownloadingGroupId(null);
    }
  };

  const columns: ColumnsType<CommandGroupRecord> = [
    { title: '指令管理名称', dataIndex: 'name', key: 'name', width: 220 },
    { title: '类型', dataIndex: 'groupType', key: 'groupType', width: 120, render: (value: CommandGroupRecord['groupType']) => <Tag color={value === 'control' ? 'blue' : 'green'}>{groupTypeLabels[value]}</Tag> },
    { title: '导出状态', dataIndex: 'exportEnabled', key: 'exportEnabled', width: 110, render: (value: boolean) => <Tag color={value ? 'gold' : 'default'}>{value ? '允许导出' : '禁止导出'}</Tag> },
    { title: '启用状态', dataIndex: 'isActive', key: 'isActive', width: 100, render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag> },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180, render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      render: (_, item) => {
        const actionState = getCommandGroupExportActionState({ group: item, downloading });

        return canDownload ? (
          <Button
            type="text"
            icon={<IconDownload />}
            loading={downloadingGroupId === item.id}
            disabled={actionState.disabled}
            title={actionState.disabledReason}
            onClick={() => void handleDownloadGroupCommands(item)}
          >
            导出指令
          </Button>
        ) : null;
      },
    },
  ];

  return (
    <Space direction="vertical" size={18} className="w-full">
      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <Space size={10} align="center">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <IconArrowBarToRight className="text-xl" />
            </div>
            <div>
              <Typography.Title level={3} className="!mb-1 !text-slate-900">导出管理</Typography.Title>
              <Typography.Text className="!text-slate-500">查看全部指令管理分组，允许导出的分组可执行导出操作。</Typography.Text>
            </div>
          </Space>
          <Space wrap>
            <Button icon={<IconReload />} onClick={() => void loadData()}>刷新</Button>
            {canDownload ? <Button type="primary" icon={<IconArrowBarToRight />} loading={downloading} onClick={() => void handleDownloadCommands()}>导出指令合集</Button> : null}
          </Space>
        </div>
      </Card>

      <Card variant="borderless" className="!rounded-xl !border !border-slate-200/70 !shadow-card">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          scroll={{ x: 900 }}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无指令管理数据" /> }}
        />
      </Card>
    </Space>
  );
};
