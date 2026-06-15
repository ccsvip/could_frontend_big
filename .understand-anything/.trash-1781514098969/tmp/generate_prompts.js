const fs = require('fs');
const p = require('path');
const r = 'C:\\SVN_CODE\\branches\\real\\could_frontend';
const d = JSON.parse(fs.readFileSync(p.join(r, '.understand-anything', 'intermediate', 'batches.json'), 'utf8'));

let c = [], cnt = 0, chks = [];
for(const b of d.batches) {
    c.push(b);
    cnt += b.files.length;
    if(cnt >= 20) {
        chks.push(c);
        c = [];
        cnt = 0;
    }
}
if(c.length > 0) chks.push(c);

chks.forEach((chk, i) => {
    fs.writeFileSync(p.join(r, '.understand-anything', 'tmp', `batch-input-${i}.json`), JSON.stringify(chk, null, 2));
});
console.log('Chunks:', chks.length);
