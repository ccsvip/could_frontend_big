import json

with open('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-2.json', 'r', encoding='utf-8') as f:
    res = json.load(f)

for r in res['results']:
    funcs = r.get('functions', [])
    classes = r.get('classes', [])
    print(f"{r['path']}: {len(funcs)} functions, {len(classes)} classes")
