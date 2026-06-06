import assert from 'node:assert/strict';
import fs from 'node:fs';

const client = fs.readFileSync('src/api/client.ts', 'utf8');

const unauthorizedBranchMatch = client.match(/if \(error\?\.response\?\.status === 401\) \{([\s\S]*?)\n    \}/);

assert(unauthorizedBranchMatch, 'client should handle 401 responses explicitly');

const unauthorizedBranch = unauthorizedBranchMatch[1];

assert(
  unauthorizedBranch.includes('handleUnauthorizedResponse();'),
  '401 responses should clear auth and redirect through handleUnauthorizedResponse',
);
assert(
  unauthorizedBranch.includes('return Promise.reject(error);'),
  '401 responses should reject immediately after clearing auth to avoid showing raw JWT token errors',
);

const branchIndex = client.indexOf(unauthorizedBranchMatch[0]);
const genericMessageIndex = client.indexOf('message.error(errorMessage)');
const branchReturnIndex = client.indexOf('return Promise.reject(error);', branchIndex);

assert(branchReturnIndex > branchIndex, '401 immediate reject should be inside the 401 branch');
assert(
  branchReturnIndex < genericMessageIndex,
  '401 immediate reject should run before generic message.error handling',
);
assert(genericMessageIndex > -1, 'non-401 errors should still use the generic message handler');

console.log('auth client unauthorized static checks passed');
