import json
with open('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batches.json', encoding='utf8') as f:
    d = json.load(f)

groups = [d['batches'][i:i+8] for i in range(0, len(d['batches']), 8)]

for group_idx, group in enumerate(groups):
    prompt = '''Analyze these files and produce GraphNode and GraphEdge objects.
Project root: C:\\SVN_CODE\\branches\\real\\could_frontend
Project: could_frontend
Languages: html, javascript, markdown, python, scss, shell, typescript
Skill directory (for bundled scripts): C:\\SVN_CODE\\branches\\real\\could_frontend\\.agents\\skills\\understand
Language directive: Generate all textual content in **zh**. Maintain technical accuracy while using natural, native-level phrasing.

For each batch listed below, you MUST perform Phase 1 (Structural Extraction) and Phase 2 (Semantic Enrichment) INDEPENDENTLY.
Write your final JSON output to C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batch-<batchIndex>.json (or parts).
You MUST NOT combine different batch indices into a single output file.

'''
    for b in group:
        idx = b['batchIndex']
        prompt += f'### BATCH {idx}\n'
        prompt += 'Pre-resolved import data for this batch:\n```json\n' + json.dumps(b.get('batchImportData', {})) + '\n```\n'
        prompt += 'Cross-batch neighbors with their exported symbols:\n```json\n' + json.dumps(b.get('neighborMap', {})) + '\n```\n'
        prompt += 'Files to analyze in this batch:\n'
        for f_info in b.get('files', []):
            prompt += f'- `{f_info["path"]}` ({f_info["sizeLines"]} lines, language: `{f_info["language"]}`, fileCategory: `{f_info["fileCategory"]}`)\n'
        prompt += '\n'
        
    with open(f'C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\prompt_group_{group_idx}.txt', 'w', encoding='utf8') as f:
        f.write(prompt)
print('Generated 5 prompt files.')
