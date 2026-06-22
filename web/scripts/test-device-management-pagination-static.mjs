import assert from 'node:assert/strict';
import fs from 'node:fs';

const api = fs.readFileSync('src/api/modules/devices.ts', 'utf8');
const page = fs.readFileSync('src/views/device-management/index.tsx', 'utf8');

assert(api.includes('page?: number;'), 'device list query should accept backend page number');
assert(api.includes('page: query?.page,'), 'device list API should pass page to backend params');

assert(page.includes('const [deviceTotal, setDeviceTotal] = useState(0);'), 'device page should keep backend total count');
assert(page.includes('const [devicePage, setDevicePage] = useState(1);'), 'device page should keep current backend page');
assert(page.includes('const devicePageRef = useRef(devicePage);'), 'realtime refresh should read the latest current page');
assert(page.includes('fetchDevices({ ...query, keyword, page })'), 'device loading should request the selected backend page');
assert(page.includes('setDeviceTotal(deviceResponse.count);'), 'device table should use backend total count');
assert(page.includes('setDevicePage(page);'), 'device table should update current page from loaded page');
assert(page.includes('void loadData(filters, 1);'), 'keyword search should restart from first backend page');
assert(page.includes('void loadData(nextFilters, 1);'), 'filter changes should restart from first backend page');
assert(page.includes('current: devicePage,'), 'table pagination should be controlled by current backend page');
assert(page.includes('total: deviceTotal,'), 'table pagination should expose backend total count');
assert(page.includes('onChange: (page) => void loadData(filters, page),'), 'pagination changes should request backend page');

console.log('device management pagination static checks passed');
