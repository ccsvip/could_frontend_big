import type { CommandGroupRecord, ControlCommandRecord, TaskCommandRecord } from '../../api/modules/commands';

type ExportableCommandRecord = {
  groupId: number;
  name: string;
  command: string;
};

export type CommandToolExportPayload = Array<{
  tool_set_name: string;
  tools: Array<{
    type: 'function';
    function: {
      name: string;
      description: string;
      parameters: {
        type: 'object';
        properties: {
          title: {
            type: 'string';
            description: string;
          };
          content: {
            type: 'string';
            description: string;
          };
        };
      };
    };
  }>;
}>;

const getGroupCommands = (
  group: CommandGroupRecord,
  controlCommands: ControlCommandRecord[],
  taskCommands: TaskCommandRecord[],
): ExportableCommandRecord[] => {
  const source = group.groupType === 'control' ? controlCommands : taskCommands;
  return source.filter((item) => item.groupId === group.id);
};

const buildExportTool = (command: ExportableCommandRecord): CommandToolExportPayload[number]['tools'][number] => {
  const commandName = command.command.trim();
  const description = command.name.trim();

  // 导出结构对齐 OpenAI tool calling 规范，字段名和层级不能增删。
  return {
    type: 'function',
    function: {
      name: commandName,
      description,
      parameters: {
        type: 'object',
        properties: {
          title: {
            type: 'string',
            description,
          },
          content: {
            type: 'string',
            description,
          },
        },
      },
    },
  };
};

export const buildCommandGroupExportPayload = (
  group: CommandGroupRecord,
  controlCommands: ControlCommandRecord[],
  taskCommands: TaskCommandRecord[],
): CommandToolExportPayload => [
  {
    tool_set_name: group.name,
    tools: getGroupCommands(group, controlCommands, taskCommands).map(buildExportTool),
  },
];

export const buildCommandGroupExportCollectionPayload = (
  groups: CommandGroupRecord[],
  controlCommands: ControlCommandRecord[],
  taskCommands: TaskCommandRecord[],
): CommandToolExportPayload =>
  groups.map((group) => ({
    tool_set_name: group.name,
    tools: getGroupCommands(group, controlCommands, taskCommands).map(buildExportTool),
  }));

export const buildCommandGroupExportFilename = (group: CommandGroupRecord, timestamp: string) => {
  const safeName = group.name.trim().replace(/[\\/:*?"<>|]/g, '_') || 'command-group';
  return `command-export-${safeName}-${timestamp}.json`;
};
