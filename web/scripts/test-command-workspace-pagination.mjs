import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const workspaceSource = readFileSync(resolve(__dirname, '../src/views/command-management/workspace.tsx'), 'utf8');
const loadCommandsStart = workspaceSource.indexOf('const loadCommands = useCallback');
const loadCommandsEnd = workspaceSource.indexOf('const loadTaskLookups = useCallback', loadCommandsStart);
const loadCommandsSource = workspaceSource.slice(loadCommandsStart, loadCommandsEnd);

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

assert(
  loadCommandsSource.includes(
    "fetchControlCommands({ page, pageSize: COMMAND_CARD_PAGE_SIZE, keyword, groupId: group.id, isActive: 'all' })",
  ),
  'workspace control command list must request only the current API page',
);

assert(
  loadCommandsSource.includes('setControlCommands(response.results);'),
  'workspace control command list must render the current API page results',
);

assert(
  loadCommandsSource.includes(
    "fetchTaskCommands({ page, pageSize: COMMAND_CARD_PAGE_SIZE, keyword, groupId: group.id, isActive: 'all' })",
  ),
  'workspace task command list must request only the current API page',
);

assert(
  loadCommandsSource.includes('setTaskCommands(response.results);'),
  'workspace task command list must render the current API page results',
);

assert(
  loadCommandsSource.includes('setCommandTotal(response.count);'),
  'workspace command pagination must keep the API total count',
);
