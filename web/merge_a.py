import re
import os

with open('web/src/views/knowledge-base/index.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the searchParams logic
content = re.sub(r'  const \[searchParams\] = useSearchParams\(\);\n  const variant = searchParams\.get\(\'variant\'\) \|\| \'A\';\n', '', content)

# Remove imports
content = content.replace("import { useSearchParams } from 'react-router-dom';\n", "")
content = content.replace("import { PrototypeSwitcher } from '../../components/PrototypeSwitcher';\n", "")
content = content.replace("import { DetailVariantA, DetailVariantB, DetailVariantC } from './DetailVariants';\n", "")

# Add missing tabler icons safely (only if not present)
for icon in ['IconFileText', 'IconPhoto', 'IconSearch', 'IconArrowLeft', 'IconDownload', 'IconGitBranch', 'IconPencil', 'IconTrash', 'IconRefresh']:
    if icon not in content:
        content = content.replace("IconAdjustments,", f"IconAdjustments,\n  {icon},")

# Add missing antd components safely
for component in ['Alert', 'Tabs']:
    if component not in content:
        content = content.replace("Button,", f"Button,\n  {component},")

# Replace return block
match = re.search(r'(\n  const detailProps = \{.*?\};\n\n  return \(\n    <>\n.*?</>\n  \);\n)', content, re.DOTALL)
if match:
    old_return = match.group(1)
    new_return = '''
  return (
    <Space direction="vertical" size={24} className="w-full pb-20">
      <div className="sticky top-[64px] z-40 bg-slate-50/90 backdrop-blur pb-4 pt-2 -mx-6 px-6 border-b border-slate-200">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <Space size={16} align="center">
            <Button type="text" icon={<IconArrowLeft />} onClick={() => setSelectedBase(null)} className="hover:bg-slate-200" />
            <div>
              <Typography.Title level={3} className="mb-0 text-slate-900">{selectedBase.name}</Typography.Title>
            </div>
            <Tag color={selectedBase.isActive ? 'success' : 'default'} className="ml-2">
              {selectedBase.isActive ? '正常工作' : '已停用'}
            </Tag>
            {canUpload && <Button type="text" icon={<IconPencil />} onClick={() => openEditBase(selectedBase)} />}
            {canDelete && (
              <Popconfirm
                title="删除知识库"
                description={`确认删除“${selectedBase.name}”及其文档吗？`}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true, loading: deletingBaseId === selectedBase.id }}
                onConfirm={() => handleDeleteBase(selectedBase)}
              >
                <Button type="text" danger loading={deletingBaseId === selectedBase.id} icon={<IconTrash />} />
              </Popconfirm>
            )}
          </Space>

          <Space wrap>
            <Input.Search
              allowClear
              placeholder="在当前库搜索文档"
              className="w-44 sm:w-52"
              onSearch={(value) => setDocumentKeyword(value.trim())}
            />
            <Button icon={<IconRefresh />} onClick={() => void loadDocuments()}>刷新</Button>
            <Button icon={<IconGitBranch />} disabled={!canUpload} loading={indexingBase} onClick={() => void handleIndexBase()}>
              重建全库索引
            </Button>
            <Button type="primary" icon={<IconDownload />} disabled={!canBulkDownload || selectedRowKeys.length === 0} loading={bulkDownloading} onClick={() => void handleBulkDownload()}>
              批量下载 ({selectedRowKeys.length})
            </Button>
          </Space>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <Tabs
          defaultActiveKey="documents"
          items={[
            {
              key: 'documents',
              label: <span className="flex items-center gap-2"><IconFileText size={16}/>文档管理</span>,
              children: documentManagementTab
            },
            {
              key: 'media',
              label: <span className="flex items-center gap-2"><IconPhoto size={16}/>配套素材</span>,
              children: mediaManagementTab
            },
            {
              key: 'recall',
              label: <span className="flex items-center gap-2"><IconSearch size={16}/>召回测试</span>,
              children: (
                <>
                  <Alert showIcon type="info" className="mb-6 rounded-xl border-brand-100 bg-brand-50/30 text-brand-800" message="验证建议" description="上线前请务必使用真实的高频业务问题进行测试。" />
                  {recallTestTab}
                </>
              )
            },
          ]}
        />
      </div>
      {mediaAssetModals}
    </Space>
  );
'''
    content = content.replace(old_return, new_return)
else:
    print('Failed to match return block')
    exit(1)

with open('web/src/views/knowledge-base/index.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

try:
    os.remove('web/src/views/knowledge-base/DetailVariants.tsx')
except Exception:
    pass
try:
    os.remove('web/src/components/PrototypeSwitcher.tsx')
except Exception:
    pass

print('Success')
