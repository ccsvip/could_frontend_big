import { readFileSync } from 'node:fs';

const layoutSource = readFileSync(new URL('../src/layouts/dashboard-layout.tsx', import.meta.url), 'utf8');

const failures = [];

const expectIncludes = (source, needle, label) => {
  if (!source.includes(needle)) {
    failures.push(`${label}: missing ${needle}`);
  }
};

const expectExcludes = (source, needle, label) => {
  if (source.includes(needle)) {
    failures.push(`${label}: should not include ${needle}`);
  }
};

expectIncludes(
  layoutSource,
  'onTitleClick: hasChildren ? () => toggleOpenBranch(menu.key) : undefined,',
  'sidebar menu open behavior',
);
expectIncludes(
  layoutSource,
  'const handleToggleOpenBranch = useCallback(',
  'sidebar menu open behavior',
);
expectIncludes(
  layoutSource,
  'const [manualOpenKeys, setManualOpenKeys] = useState<string[] | null>(null);',
  'sidebar menu open behavior',
);
expectIncludes(
  layoutSource,
  'const openKeys = manualOpenKeys ?? activeOpenKeys;',
  'sidebar menu open behavior',
);
expectExcludes(
  layoutSource,
  'Array.from(new Set([...manualOpenKeys, ...activeOpenKeys]))',
  'sidebar menu open behavior',
);
expectExcludes(
  layoutSource,
  'onOpenChange={handleOpenChange}',
  'sidebar menu open behavior',
);

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log('sidebar open key static checks passed');
