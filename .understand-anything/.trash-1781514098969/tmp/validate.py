import json

with open('.understand-anything/tmp/batch-input-16.json', 'r', encoding='utf8') as f:
    input_data = json.load(f)[0]

batch_import_data = input_data.get('batchImportData', {})
neighbor_map = input_data.get('neighborMap', {})

def validate_part(path):
    with open(path, 'r', encoding='utf8') as f:
        data = json.load(f)
    
    node_ids = {n['id'] for n in data['nodes']}
    valid = True
    
    for edge in data['edges']:
        for ref in [edge['source'], edge['target']]:
            if ref in node_ids:
                continue
            
            if ref.startswith('file:'):
                file_path = ref[5:]
                if file_path in neighbor_map or file_path in batch_import_data:
                    continue
                
                # Check if it's imported
                is_imported = False
                for imports in batch_import_data.values():
                    if file_path in imports:
                        is_imported = True
                        break
                if is_imported:
                    continue
                
                print(f"Invalid ref {ref} in {path}")
                valid = False
            else:
                print(f"Invalid non-file ref {ref} in {path}")
                valid = False
    return valid

print("p1:", validate_part('.understand-anything/intermediate/batch-36-part-1.json'))
print("p2:", validate_part('.understand-anything/intermediate/batch-36-part-2.json'))
