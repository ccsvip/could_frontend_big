import re

with open('web/src/views/knowledge-base/index.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
imports = '''import { useSearchParams } from 'react-router-dom';
import { PrototypeSwitcher } from '../../components/PrototypeSwitcher';
import { DetailVariantA, DetailVariantB, DetailVariantC } from './DetailVariants';
'''
content = content.replace('import { useCallback, useEffect, useMemo, useRef, useState } from \'react\';', 'import { useCallback, useEffect, useMemo, useRef, useState } from \'react\';\n' + imports)

# Find the end of the `if (!selectedBase)` return block
# It starts around line 1524: `  return (`
match = re.search(r'(\n  return \(\n    <Space direction="vertical" size=\{32\}.*?);\n\};\n', content, re.DOTALL)
if not match:
    print('Failed to find detail view return block in index.tsx')
    exit(1)

old_return = match.group(1)

new_return = '''
  const [searchParams] = useSearchParams();
  const variant = searchParams.get('variant') || 'A';

  const detailProps = {
    selectedBase, setSelectedBase, canUpload, canDelete, canBulkDownload,
    openEditBase, deletingBaseId, handleDeleteBase, setDocumentKeyword,
    loadDocuments, indexingBase, handleIndexBase, selectedRowKeys,
    bulkDownloading, handleBulkDownload, documentManagementTab,
    mediaManagementTab, recallTestTab, mediaAssetModals
  };

  return (
    <>
      {variant === 'A' && <DetailVariantA {...detailProps} />}
      {variant === 'B' && <DetailVariantB {...detailProps} />}
      {variant === 'C' && <DetailVariantC {...detailProps} />}
      <PrototypeSwitcher variants={['A', 'B', 'C']} current={variant} />
    </>
  );
'''

content = content.replace(old_return, new_return)

with open('web/src/views/knowledge-base/index.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Successfully refactored index.tsx for detail variants')
