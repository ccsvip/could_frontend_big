import fs from 'node:fs';

const read = (path) => fs.readFileSync(path, 'utf8');

const layout = read('src/layouts/dashboard-layout.tsx');
const router = read('src/router/index.tsx');
const resourcesApi = read('src/api/modules/resources.ts');
const settingsApi = read('src/api/modules/settings.ts');
const settingsPage = read('src/views/minio-settings/index.tsx');
const resourcePage = read('src/views/resource-management/index.tsx');

const checks = [
  {
    name: 'super admin menu includes settings parent and MinIO child',
    ok: layout.includes("key: 'settings'") && layout.includes("path: '/settings/minio'") && layout.includes("label: 'MinIO 设置'"),
  },
  {
    name: 'router protects MinIO settings route with super admin permission',
    ok: router.includes("path: 'settings/minio'") && router.includes('<MinioSettingsPage />') && router.includes('tenant.management.view'),
  },
  {
    name: 'settings API uses platform endpoint',
    ok: settingsApi.includes("'/settings/minio/'") && settingsApi.includes('fetchMinioSettings') && settingsApi.includes('updateMinioSettings'),
  },
  {
    name: 'settings API supports tenant video quotas',
    ok: settingsApi.includes("'/settings/minio/quotas/'") && settingsApi.includes('fetchTenantVideoQuotas') && settingsApi.includes('updateTenantVideoQuotas'),
  },
  {
    name: 'settings page edits MinIO fields',
    ok: settingsPage.includes('fetchMinioSettings') && settingsPage.includes('updateMinioSettings') && settingsPage.includes('bucketName') && settingsPage.includes('secretKey') && settingsPage.includes('allowVideoCloudUrl'),
  },
  {
    name: 'settings page edits per-tenant video quotas',
    ok: settingsPage.includes('quotaRows') && settingsPage.includes('quotaLimited') && settingsPage.includes('updateTenantVideoQuotas') && settingsPage.includes('Table<TenantVideoQuotaRecord>'),
  },
  {
    name: 'resources API supports objectKey direct upload',
    ok: resourcesApi.includes('objectKey?: string') && resourcesApi.includes('objectSize?: number | null') && resourcesApi.includes('presignVideoUpload') && resourcesApi.includes('uploadFileToPresignedUrl'),
  },
  {
    name: 'video resource form uploads to MinIO with progress and quota display',
    ok: resourcePage.includes('uploadVideoToMinio')
      && resourcePage.includes('objectKey: objectKey || undefined')
      && resourcePage.includes('objectSize')
      && resourcePage.includes('<Progress')
      && resourcePage.includes('uploadAbortRef')
      && resourcePage.includes('remainingBytes'),
  },
  {
    name: 'video resource form gates cloud URL and file upload as mutually exclusive',
    ok: resourcesApi.includes('allowCloudUrl')
      && settingsApi.includes('allowVideoCloudUrl')
      && resourcePage.includes('showCloudUrlField')
      && resourcePage.includes('上传视频和云端 URL 只能二选一'),
  },
  {
    name: 'video resource form requires local upload when cloud URL is hidden',
    ok: resourcePage.includes("'请上传视频'")
      && !resourcePage.includes('上传视频和云端URL都为选填'),
  },
  {
    name: 'video resource form requires one video source when cloud URL is visible',
    ok: resourcePage.includes('请上传视频或填写云端 URL'),
  },
];

const failures = checks.filter((check) => !check.ok);

if (failures.length > 0) {
  failures.forEach((failure) => {
    console.error(`FAIL ${failure.name}`);
  });
  process.exit(1);
}

checks.forEach((check) => {
  console.log(`PASS ${check.name}`);
});
