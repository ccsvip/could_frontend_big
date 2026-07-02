const fs = require('fs');
const path = require('path');

function walk(dir) {
  let r = [];
  fs.readdirSync(dir).forEach(f => {
    let dirPath = path.join(dir, f);
    if(fs.statSync(dirPath).isDirectory()) {
      r = r.concat(walk(dirPath));
    } else if(f.endsWith('.tsx')) {
      r.push(dirPath);
    }
  });
  return r;
}

const files = walk('./web/src');
let fixCount = 0;

files.forEach(f => {
  let content = fs.readFileSync(f, 'utf8');
  let modified = false;

  // Regex to find `<Component ... className="... w-40 ..."`
  const classRegex = /(<(?:Input|Select|DatePicker|Button|RangePicker|InputNumber|Search)[^>]*className=["'])([^"']*)(\b(?:w-32|w-40|w-48|w-56|w-64|w-72|w-80|w-96)\b)([^"']*["'])/g;
  
  if (classRegex.test(content)) {
    content = content.replace(classRegex, (match, p1, p2, p3, p4) => {
      if (p2.includes('sm:w-') || p4.includes('sm:w-') || p2.includes('w-full') || p4.includes('w-full')) return match;
      modified = true;
      return p1 + p2 + 'w-full sm:' + p3 + p4;
    });
  }

  const minwRegex = /(<(?:Input|Select|DatePicker|Button|RangePicker|InputNumber|Search)[^>]*className=["'])([^"']*)(\bmin-w-\[[0-9]+px\]\b)([^"']*["'])/g;
  
  if (minwRegex.test(content)) {
    content = content.replace(minwRegex, (match, p1, p2, p3, p4) => {
      if (p2.includes('w-full') || p4.includes('w-full')) return match;
      modified = true;
      return p1 + p2 + 'w-full sm:' + p3 + p4;
    });
  }

  if (modified) {
    fs.writeFileSync(f, content);
    console.log('Fixed responsive widths in ' + f);
    fixCount++;
  }
});

console.log('Total files fixed:', fixCount);
