import json

with open(r'C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-extract-results-1.json', 'r', encoding='utf-8') as f:
    res = json.load(f)

for file in res.get('results', []):
    print(f"FILE: {file['path']} ({file.get('fileCategory')})")
    
    for f_node in file.get('functions', []):
        lines = f_node.get('endLine', 0) - f_node.get('startLine', 0) + 1
        is_exported = any(e.get('name') == f_node['name'] for e in file.get('exports', []))
        if lines >= 10 or is_exported:
            print(f"  FUNC: {f_node['name']} (lines: {lines}, exported: {is_exported})")
            
    for c_node in file.get('classes', []):
        lines = c_node.get('endLine', 0) - c_node.get('startLine', 0) + 1
        is_exported = any(e.get('name') == c_node['name'] for e in file.get('exports', []))
        methods = len(c_node.get('methods', []))
        if lines >= 20 or methods >= 2 or is_exported:
            print(f"  CLASS: {c_node['name']} (lines: {lines}, methods: {methods}, exported: {is_exported})")
