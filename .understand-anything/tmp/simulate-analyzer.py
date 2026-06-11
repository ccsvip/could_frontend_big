import json
import subprocess
import os

with open('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batches.json', encoding='utf8') as f:
    d = json.load(f)

for b in d['batches']:
    idx = b['batchIndex']
    
    # 1. Prepare input JSON
    in_data = {
        "projectRoot": "C:\\SVN_CODE\\branches\\real\\could_frontend",
        "batchFiles": b['files'],
        "batchImportData": b.get('batchImportData', {})
    }
    in_path = f'C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-analyzer-input-{idx}.json'
    out_path = f'C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-analyzer-output-{idx}.json'
    
    with open(in_path, 'w', encoding='utf8') as f:
        json.dump(in_data, f)
        
    # 2. Run extract-structure.mjs
    subprocess.run([
        'node', 
        'C:\\SVN_CODE\\branches\\real\\could_frontend\\.agents\\skills\\understand\\extract-structure.mjs',
        in_path,
        out_path
    ], check=True)
    
    pass

print("Finished running extract-structure.mjs for all batches!")
