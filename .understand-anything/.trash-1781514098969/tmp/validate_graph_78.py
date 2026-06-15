import json
import glob
import os

files = glob.glob('.understand-anything/intermediate/batch-7*.json') + glob.glob('.understand-anything/intermediate/batch-8*.json')

has_error = False
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    
    node_ids = {n['id'] for n in nodes}
    for e in edges:
        if e['source'] not in node_ids:
            print(f"Validation failed in {filepath}: Edge {e} has source not in nodes.")
            has_error = True

if not has_error:
    print("Validation passed for batch 7 and 8.")
