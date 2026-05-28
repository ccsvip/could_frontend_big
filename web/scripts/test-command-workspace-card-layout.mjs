import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const workspaceSource = readFileSync(resolve(__dirname, '../src/views/command-management/workspace.tsx'), 'utf8');

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

assert(
  workspaceSource.includes('const COMMAND_CARD_PAGE_SIZE = 8;'),
  'workspace command card pagination must use an explicit page size of 8',
);

assert(
  workspaceSource.includes('Pagination,'),
  'workspace must use Ant Design Pagination for command cards over 8 items',
);

assert(
  workspaceSource.includes('paginatedControlCommands') &&
    workspaceSource.includes('const paginatedControlCommands = controlCommands;'),
  'control command cards must render the server-paginated current page',
);

assert(
  workspaceSource.includes('paginatedTaskCommands') &&
    workspaceSource.includes('const paginatedTaskCommands = taskCommands;'),
  'task command cards must render the server-paginated current page',
);

assert(
  workspaceSource.includes('total={commandTotal}'),
  'workspace command card pagination must use the API total count',
);

assert(
  workspaceSource.includes('setCommandPage(1);'),
  'workspace must reset command card pagination when group or search context changes',
);

assert(
  workspaceSource.includes('max-h-[calc(100vh-390px)] overflow-y-auto pr-1'),
  'left group cards must have a bounded scroll container separate from the search input',
);
