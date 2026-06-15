import json
import glob

files = glob.glob('.understand-anything/intermediate/batch-*.json')

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    
    node_ids = {n['id'] for n in nodes}
    for e in edges:
        if e['source'] not in node_ids:
            print(f"Validation failed in {filepath}: Edge {e} has source not in nodes.")

print("Validation completed.")
