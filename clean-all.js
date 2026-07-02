const fs = require('fs');

const files = [
  'web/src/views/application-management/index.tsx',
  'web/src/views/device-management/index.tsx',
  'web/src/views/resource-management/index.tsx',
  'web/src/views/command-management/index.tsx',
  'web/src/views/command-management/workspace.tsx',
  'web/src/views/model-management/index.tsx'
];

for (const path of files) {
  if (!fs.existsSync(path)) {
    console.log('Skipping ' + path);
    continue;
  }
  let content = fs.readFileSync(path, 'utf8');

  // Replace ! in className="..."
  content = content.replace(/className="([^"]*)"/g, (match, classes) => {
      return `className="${classes.replace(/!([a-z0-9\[\]-]+)/g, '$1')}"`;
  });

  // Replace ! in className={`...`}
  content = content.replace(/className=\{`([^`]+)`\}/g, (match, classes) => {
      return `className={\`${classes.replace(/!([a-z0-9\[\]-]+)/g, '$1')}\`}`;
  });

  // Replace ! in className={'...'} or conditional operators
  content = content.replace(/'!([a-z0-9\[\]-]+)([^']*)'/g, (match, prefix, rest) => {
      return `'${prefix}${rest}'`.replace(/!([a-z0-9\[\]-]+)/g, '$1');
  });

  fs.writeFileSync(path, content);
  console.log('Processed ' + path);
}
