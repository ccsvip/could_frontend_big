const fs=require('fs');
const s=JSON.parse(fs.readFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-scan-files.json'));
fs.writeFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-import-map-input.json', JSON.stringify({projectRoot:'C:\\SVN_CODE\\branches\\real\\could_frontend',files:s.files}));
