import re

with open('web/src/views/knowledge-base/index.bak.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Match the Create Modal
match = re.search(r'(\s*<Modal\s+title="创建知识库".*?</Modal>)', content, re.DOTALL)
if match:
    create_modal_code = match.group(1)
    
    with open('web/src/views/knowledge-base/index.tsx', 'r', encoding='utf-8') as f:
        current = f.read()
    
    insert_str = '\n  const createBaseModal = (' + create_modal_code + '\n  );\n'
    
    current = current.replace('  const documentManagementTab = (', insert_str + '\n  const documentManagementTab = (')
    
    current = current.replace('{editBaseModal}', '{editBaseModal}\n        {createBaseModal}')

    # Also restore the missing unused variables that I stripped earlier
    # previewBaseId, setPreviewBaseId, createOpen, setCreateOpen, createSaving, setCreateSaving, 
    # deletingBaseId, setDeletingBaseId, handleCreateBase, openEditBase, handleDeleteBase

    # Actually they are needed by the new code, so let's check if they exist, if not, wait I just deleted them!
    # I should restore them from the backup file.
    
    state_vars = [
        r'(const \[previewBaseId, setPreviewBaseId\] = useState<number \| null>\(null\);)',
        r'(const \[createOpen, setCreateOpen\] = useState\(false\);)',
        r'(const \[createSaving, setCreateSaving\] = useState\(false\);)',
        r'(const \[deletingBaseId, setDeletingBaseId\] = useState<number \| null>\(null\);)'
    ]
    funcs = [
        r'(const handleCreateBase = async \(\) => \{.*?\n  \};\n)',
        r'(const openEditBase = useCallback\(\(item: KnowledgeBaseRecord\) => \{.*?\n  \}\), \[editForm\]\);\n)',
        r'(const handleDeleteBase = useCallback\(async \(item: KnowledgeBaseRecord\) => \{.*?\n  \}\), \[loadBases, selectedBase\]\);\n)'
    ]
    
    for var in state_vars:
        m = re.search(var, content)
        if m and m.group(1) not in current:
            current = current.replace('const [editForm] = Form.useForm<KnowledgeBaseFormValues>();', 'const [editForm] = Form.useForm<KnowledgeBaseFormValues>();\n  ' + m.group(1))

    for func in funcs:
        m = re.search(func, content, re.DOTALL)
        if m and m.group(1)[:20] not in current:
            current = current.replace('const handleEditBase = async () => {', m.group(1) + '\n\n  const handleEditBase = async () => {')

    # Also fix implicit any on openEditBase and handleDeleteBase just in case
    current = current.replace('const openEditBase = useCallback((item: KnowledgeBaseRecord) => {', 'const openEditBase = useCallback((item: any) => {')
    current = current.replace('const handleDeleteBase = useCallback(async (item: KnowledgeBaseRecord) => {', 'const handleDeleteBase = useCallback(async (item: any) => {')


    with open('web/src/views/knowledge-base/index.tsx', 'w', encoding='utf-8') as f:
        f.write(current)
    
    print('Successfully inserted createBaseModal and restored vars')
else:
    print('Failed to find create base modal')
