import { Collapse, Popover } from 'antd';
import { IconBook, IconFileText } from '@tabler/icons-react';

import type { KnowledgeReference } from '../api/modules/chat';

type KnowledgeReferencesProps = {
  references: KnowledgeReference[];
};

export const KnowledgeReferences = ({ references }: KnowledgeReferencesProps) => {
  if (!references.length) return null;

  const groups = new Map<string, { name: string; knowledgeBaseName: string; references: KnowledgeReference[] }>();
  for (const reference of references) {
    const key = reference.documentId > 0 ? String(reference.documentId) : reference.documentName;
    const current = groups.get(key);
    if (current) {
      current.references.push(reference);
    } else {
      groups.set(key, {
        name: reference.documentName || `文档 #${reference.documentId}`,
        knowledgeBaseName: reference.knowledgeBaseName,
        references: [reference],
      });
    }
  }
  const documents = [...groups.values()];
  const content = (
    <div className="max-h-[min(70vh,560px)] w-[min(82vw,520px)] overflow-y-auto custom-scrollbar">
      <Collapse
        ghost
        size="small"
        items={documents.map((document, documentIndex) => ({
          key: `${document.name}-${documentIndex}`,
          label: (
            <div className="min-w-0">
              <div className="truncate text-fluid-sm font-semibold text-slate-700">{document.name}</div>
              <div className="text-fluid-xs text-slate-400">
                {document.knowledgeBaseName || '知识库'} · {document.references.length} 个切片
              </div>
            </div>
          ),
          children: (
            <div className="space-y-3">
              {document.references.map((reference) => (
                <div key={`${reference.position}-${reference.chunkId || reference.chunkIndex || 0}`} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-fluid-xs text-slate-400">
                    <span className="font-mono">引用 #{reference.position}</span>
                    {reference.score !== null ? <span>相关度 {(reference.score * 100).toFixed(1)}%</span> : null}
                  </div>
                  <div className="whitespace-pre-wrap break-words text-fluid-sm leading-relaxed text-slate-600">{reference.content}</div>
                </div>
              ))}
            </div>
          ),
        }))}
      />
    </div>
  );

  return (
    <Popover content={content} trigger="click" placement="bottomLeft">
      <button type="button" className="mt-2 flex max-w-full items-center gap-2 rounded-xl border border-brand-100 bg-brand-50 px-3 py-1.5 text-fluid-xs text-brand-700 transition-colors hover:border-brand-200">
        <IconBook size={15} className="shrink-0" />
        <span className="font-semibold">知识引用 · {documents.length} 个文档</span>
        <span className="flex min-w-0 items-center gap-1 truncate text-brand-600">
          <IconFileText size={14} className="shrink-0" />
          {documents.map((item) => item.name).join('、')}
        </span>
      </button>
    </Popover>
  );
};
