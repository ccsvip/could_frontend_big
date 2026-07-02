const fs = require('fs');
const path = require('path');

function processFile(filePath) {
    let content = fs.readFileSync(filePath, 'utf8');

    // Replace ! in className="..."
    content = content.replace(/className="([^"]*)"/g, (match, classes) => {
        return `className="${classes.replace(/!([a-z0-9\[\]-]+)/g, '$1')}"`;
    });

    // Replace ! in className={`...`}
    content = content.replace(/className=\{`([^`]+)`\}/g, (match, classes) => {
        return `className={\`${classes.replace(/!([a-z0-9\[\]-]+)/g, '$1')}\`}`;
    });

    // Replace ! in conditional operators
    content = content.replace(/'!([a-z0-9\[\]-]+)([^']*)'/g, (match, prefix, rest) => {
        return `'${prefix}${rest}'`.replace(/!([a-z0-9\[\]-]+)/g, '$1');
    });

    fs.writeFileSync(filePath, content);
}

function walkSync(currentDirPath) {
    fs.readdirSync(currentDirPath).forEach(function (name) {
        var filePath = path.join(currentDirPath, name);
        var stat = fs.statSync(filePath);
        if (stat.isFile() && filePath.endsWith('.tsx')) {
            processFile(filePath);
        } else if (stat.isDirectory()) {
            walkSync(filePath);
        }
    });
}

walkSync('web/src');
console.log('Processed all tsx files');
