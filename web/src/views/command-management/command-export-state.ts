type CommandGroupPage<T> = {
  next: string | null;
  results: T[];
};

export type CommandGroupPageFetcher<T> = (page: number) => Promise<CommandGroupPage<T>>;

export const collectCommandGroupPages = async <T,>(fetcher: CommandGroupPageFetcher<T>) => {
  // 分组接口默认分页，导出管理需要主动收集完整列表。
  const results: T[] = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const response = await fetcher(page);
    results.push(...response.results);
    hasNext = Boolean(response.next);
    page += 1;
  }

  return results;
};

export const getCommandGroupExportActionState = ({
  group,
  downloading,
}: {
  group: { exportEnabled: boolean };
  downloading: boolean;
}) => {
  // 禁止导出不隐藏分组和操作入口，只禁用具体导出按钮。
  if (!group.exportEnabled) {
    return {
      disabled: true,
      disabledReason: '该指令管理已禁止导出',
    };
  }

  return {
    disabled: downloading,
    disabledReason: undefined,
  };
};
