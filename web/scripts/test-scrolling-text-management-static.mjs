import fs from 'node:fs';

const read = (path) => fs.readFileSync(path, 'utf8');

const page = read('src/views/scrolling-text-management/index.tsx');
const styles = read('src/styles/index.css');

const checks = [
  {
    name: 'list query is fixed to the first page',
    ok: page.includes("() => ({ page: 1, title: titleFilter, keyword, status: statusFilter, lang: 'zh' })")
      && !page.includes('const [page, setPage]')
      && !page.includes('const [pageSize]')
      && !page.includes('const [total, setTotal]'),
  },
  {
    name: 'pagination component is removed from scrolling text page',
    ok: !page.includes('Pagination,')
      && !page.includes('<Pagination')
      && !page.includes('onChange={(nextPage) => setPage(nextPage)}'),
  },
  {
    name: 'record limit is refreshed and create is disabled only after one is known to exist',
    ok: page.includes('existingRecordCount')
      && page.includes('refreshRecordLimit')
      && page.includes('const canOpenCreate = existingRecordCount === null || existingRecordCount === 0')
      && page.includes('disabled={!canOpenCreate}')
      && page.includes("fetchScrollingTexts({ page: 1, status: 'all', lang: 'zh' })"),
  },
  {
    name: 'search and status changes do not reset pagination state',
    ok: !page.includes('setPage(1)') && !page.includes('setPage((current) => current - 1)'),
  },
  {
    name: 'form modal uses responsive width and scrolling class',
    ok: page.includes('width="min(92vw, 56rem)"')
      && page.includes('className="scrolling-text-form-modal"')
      && styles.includes('.scrolling-text-form-modal .ant-modal-content')
      && styles.includes('.scrolling-text-form-modal .ant-modal-body')
      && styles.includes('max-height: 68vh')
      && styles.includes('overflow-y: auto'),
  },
  {
    name: 'form list supports inserting a new item above the current one',
    ok: page.includes('index > 0')
      && page.includes("add({ order: index + 1, zh: '', en: '' }, index)")
      && page.includes('向上插入'),
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
