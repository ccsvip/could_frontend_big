const fs = require('fs');

const path = 'web/src/views/knowledge-base/index.tsx';
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
console.log('Done');
