const fs = require('fs');
const path = require('path');

const root = 'C:\\SVN_CODE\\branches\\real\\could_frontend';
const tmpDir = path.join(root, '.understand-anything', 'tmp');
const outDir = path.join(root, '.understand-anything', 'intermediate');

const scanData = JSON.parse(fs.readFileSync(path.join(tmpDir, 'ua-scan-files.json'), 'utf8'));
const importData = JSON.parse(fs.readFileSync(path.join(tmpDir, 'ua-import-map-output.json'), 'utf8'));

if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
}

const langs = Object.keys(scanData.stats.byLanguage);
if (!langs.includes("json")) langs.push("json");
const languages = langs.filter(l => l !== 'unknown' && l !== 'config').sort();

const result = {
    name: "could_frontend",
    description: "数字人后台管理平台（solin）：基于 React 18 + Vite 的单页应用与 Django 5.2 + DRF + Celery 架构，通过 docker-compose 编排部署的多容器全栈项目。 注意：此项目包含超过 100 个源文件；建议将分析范围缩小到特定子目录以获得更快的分析结果。",
    languages: languages,
    frameworks: ["celery", "django", "djangorestframework", "Docker", "Docker Compose", "react", "tailwindcss", "uvicorn", "vite", "zustand"],
    files: scanData.files,
    totalFiles: scanData.totalFiles,
    filteredByIgnore: scanData.filteredByIgnore,
    estimatedComplexity: scanData.estimatedComplexity,
    importMap: importData.importMap
};

fs.writeFileSync(path.join(outDir, 'scan-result.json'), JSON.stringify(result, null, 2), 'utf8');
console.log('Successfully assembled scan-result.json');
