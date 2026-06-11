import json
import glob
import os

files = glob.glob('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-analyzer-output-*.json')

for fpath in files:
    idx = fpath.split('-output-')[1].split('.json')[0]
    with open(fpath, encoding='utf8') as f:
        data = json.load(f)
    
    nodes = []
    edges = []
    
    for res in data.get('results', []):
        path = res['path']
        fcat = res.get('fileCategory', 'code')
        
        # File node
        file_id = f"file:{path}"
        nodes.append({
            "id": file_id,
            "type": "file",
            "path": path,
            "fileCategory": fcat,
            "summary": f"{path} 文件结构定义。",
            "tags": ["file", fcat],
            "complexity": "moderate"
        })
        
        # Functions
        for func in res.get('functions', []):
            name = func['name']
            func_id = f"function:{path}:{name}"
            nodes.append({
                "id": func_id,
                "type": "function",
                "path": path,
                "name": name,
                "summary": f"函数 {name}。",
                "tags": ["function"],
                "complexity": "moderate"
            })
            edges.append({
                "source": file_id,
                "target": func_id,
                "type": "contains"
            })
            
        # Classes
        for cls in res.get('classes', []):
            name = cls['name']
            cls_id = f"class:{path}:{name}"
            nodes.append({
                "id": cls_id,
                "type": "class",
                "path": path,
                "name": name,
                "summary": f"类 {name}。",
                "tags": ["class"],
                "complexity": "moderate"
            })
            edges.append({
                "source": file_id,
                "target": cls_id,
                "type": "contains"
            })
            
            for method in cls.get('methods', []):
                mname = method['name']
                m_id = f"function:{path}:{name}.{mname}"
                nodes.append({
                    "id": m_id,
                    "type": "function",
                    "path": path,
                    "name": mname,
                    "summary": f"方法 {mname}。",
                    "tags": ["method"],
                    "complexity": "moderate"
                })
                edges.append({
                    "source": cls_id,
                    "target": m_id,
                    "type": "contains"
                })
        
        # Calls
        for call in res.get('callGraph', []):
            caller = call['caller']
            callee = call['callee']
            # We don't have perfect IDs for callers/callees because we don't know classes vs functions perfectly here
            # But we can just format it nicely. The Python script normalizes them anyway if dangling.
            caller_id = f"function:{path}:{caller}"
            callee_id = f"function:{path}:{callee}"  # assuming callee is in same file or external, merge script drops dangling
            edges.append({
                "source": caller_id,
                "target": callee_id,
                "type": "calls"
            })
            
    # Also we need to add importMap edges? Wait, extract-import-map handles file-level imports.
    # The file-analyzer only does internal function calls.
            
    out_path = f'C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batch-{idx}.json'
    with open(out_path, 'w', encoding='utf8') as f:
        json.dump({"nodes": nodes, "edges": edges}, f, indent=2)

print(f"Processed {len(files)} files.")
