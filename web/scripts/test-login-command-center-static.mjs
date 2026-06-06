import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const loginSource = readFileSync(resolve(__dirname, '../src/views/login/index.tsx'), 'utf8');

assert(
  loginSource.includes("import loginCommandCenterImage from '../../assets/login-command-center.png';"),
  'login page must import the new command center hero asset',
);

assert(
  !loginSource.includes("import heroLayerImage from '../../assets/hero.png';"),
  'login page must stop depending on the old small hero icon',
);

assert(
  loginSource.includes('const commandCenterNodes = ['),
  'login page must define command center visual nodes for the hero scene',
);

assert(
  loginSource.includes('const operationSignals = ['),
  'login page must define operation signal summaries for the first screen',
);

assert(
  loginSource.includes('aria-label="数字人运维指挥中心主视觉"'),
  'hero scene must expose a stable accessible label',
);

assert(
  loginSource.includes('数字人运维指挥中心'),
  'login first screen must present the command center positioning',
);

assert(
  loginSource.includes('账号入驻申请') &&
    loginSource.includes('提交申请') &&
    loginSource.includes('取消'),
  'account application modal must keep the existing application flow labels',
);

assert(
  loginSource.includes('onFinish={onSubmit}') &&
    loginSource.includes('loginRequest(values)') &&
    loginSource.includes("navigate('/devices', { replace: true })"),
  'login form behavior must keep the existing submit request and navigation',
);

console.log('login command center static checks passed');
