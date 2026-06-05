import assert from 'node:assert/strict';
import fs from 'node:fs';

const auditApi = fs.readFileSync('src/api/modules/audit.ts', 'utf8');
const router = fs.readFileSync('src/router/index.tsx', 'utf8');
const page = fs.readFileSync('src/views/log-management/index.tsx', 'utf8');

assert(auditApi.includes('description: string;'), 'OperationLogRecord should expose description');
assert(auditApi.includes('clearOperationLogs'), 'audit API should expose clearOperationLogs');
assert(router.includes('permission="audit.logs.view"'), 'logs route should use audit.logs.view guard');
assert(page.includes('操作具体做了什么'), 'log table should show operation detail column');
assert(page.includes('无法恢复'), 'clear modal should warn that deletion cannot be recovered');
assert(!page.includes("title: '请求路径'"), 'log table should not expose request path as a main column');

console.log('audit log management static checks passed');
