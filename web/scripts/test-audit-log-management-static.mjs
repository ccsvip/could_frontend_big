import assert from 'node:assert/strict';
import fs from 'node:fs';

const page = fs.readFileSync('src/views/log-management/index.tsx', 'utf8');

assert(page.includes("import { DeleteOutlined, FileSearchOutlined } from '@ant-design/icons';"), 'page should import the clear and search icons');
assert(page.includes("import { Button, Card, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';"), 'page should import the expected antd controls');
assert(page.includes('clearOperationLogs'), 'page should call clearOperationLogs');
assert(page.includes("const isPlatformAdmin = hasPermission('tenant.management.view') || !tenant;"), 'page should derive platform admin scope from auth store');
assert(page.includes("content: isPlatformAdmin"), 'clear modal should distinguish platform-wide and tenant-scoped deletion');
assert(page.includes("title: '操作具体做了什么'"), 'log table should show backend description column');
assert(page.includes("render: (value: string) => value || <span className=\"text-slate-400\">-</span>"), 'description column should fall back to a dash');
assert(!page.includes("describeOperationPath"), 'frontend path-description logic should be removed');
assert(!page.includes("methodColorMap"), 'request method color mapping should be removed');
assert(!page.includes("statusColor"), 'status code color mapping should be removed');
assert(!page.includes("fallbackActionText"), 'fallback action text logic should be removed');
assert(!page.includes("pathDescriptionRules"), 'path description rules should be removed');

console.log('audit log management static checks passed');
