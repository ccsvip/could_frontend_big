import { message } from 'antd';
import { type MouseEvent, useMemo } from 'react';

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const applyInlineMarkdown = (value: string) => {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
};

const isHorizontalRule = (line: string) => /^(?:-{3,}|\*{3,}|_{3,})$/.test(line.trim());

const isTableSeparator = (line: string) => /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/.test(line);

const splitTableCells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());

const buildTableHtml = (headerLine: string, bodyLines: string[]) => {
  const headers = splitTableCells(headerLine);
  const rows = bodyLines.map(splitTableCells);
  const headerHtml = headers.map((cell) => `<th>${applyInlineMarkdown(cell)}</th>`).join('');
  const bodyHtml = rows
    .map((cells) => `<tr>${cells.map((cell) => `<td>${applyInlineMarkdown(cell)}</td>`).join('')}</tr>`)
    .join('');
  return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
};

const buildCodeBlockHtml = (code: string) => {
  const encoded = encodeURIComponent(code);
  return [
    '<div class="chat-code-block">',
    `<button type="button" class="chat-code-copy-btn" data-copy-code="${encoded}">复制代码</button>`,
    `<pre><code>${escapeHtml(code)}</code></pre>`,
    '</div>',
  ].join('');
};

const renderMarkdownToHtml = (markdown: string) => {
  const normalized = markdown.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const htmlParts: string[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let inUnorderedList = false;
  let inOrderedList = false;

  const closeLists = () => {
    if (inUnorderedList) {
      htmlParts.push('</ul>');
      inUnorderedList = false;
    }
    if (inOrderedList) {
      htmlParts.push('</ol>');
      inOrderedList = false;
    }
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim().startsWith('```')) {
      closeLists();
      if (inCodeBlock) {
        htmlParts.push(buildCodeBlockHtml(codeLines.join('\n')));
        inCodeBlock = false;
        codeLines = [];
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      closeLists();
      continue;
    }

    if (isHorizontalRule(line)) {
      closeLists();
      htmlParts.push('<hr />');
      continue;
    }

    if (
      line.includes('|')
      && index + 1 < lines.length
      && isTableSeparator(lines[index + 1])
    ) {
      closeLists();
      const bodyLines: string[] = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        bodyLines.push(lines[index]);
        index += 1;
      }
      index -= 1;
      htmlParts.push(buildTableHtml(line, bodyLines));
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      closeLists();
      const level = headingMatch[1].length;
      htmlParts.push(`<h${level}>${applyInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const unorderedMatch = line.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      if (!inUnorderedList) {
        closeLists();
        htmlParts.push('<ul>');
        inUnorderedList = true;
      }
      htmlParts.push(`<li>${applyInlineMarkdown(unorderedMatch[1])}</li>`);
      continue;
    }

    const orderedMatch = line.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      if (!inOrderedList) {
        closeLists();
        htmlParts.push('<ol>');
        inOrderedList = true;
      }
      htmlParts.push(`<li>${applyInlineMarkdown(orderedMatch[1])}</li>`);
      continue;
    }

    const quoteMatch = line.match(/^>\s?(.+)$/);
    if (quoteMatch) {
      closeLists();
      htmlParts.push(`<blockquote><p>${applyInlineMarkdown(quoteMatch[1])}</p></blockquote>`);
      continue;
    }

    closeLists();
    htmlParts.push(`<p>${applyInlineMarkdown(line)}</p>`);
  }

  if (inCodeBlock) {
    htmlParts.push(buildCodeBlockHtml(codeLines.join('\n')));
  }

  closeLists();
  return htmlParts.join('');
};

type ChatMarkdownProps = {
  content: string;
  className?: string;
};

export const ChatMarkdown = ({ content, className }: ChatMarkdownProps) => {
  const html = useMemo(() => renderMarkdownToHtml(content), [content]);

  const handleCopyCode = async (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    const button = target.closest<HTMLButtonElement>('[data-copy-code]');
    if (!button) return;
    const encoded = button.dataset.copyCode;
    if (!encoded) return;
    try {
      await navigator.clipboard.writeText(decodeURIComponent(encoded));
      message.success('代码已复制');
    } catch {
      message.error('复制代码失败');
    }
  };

  return (
    <div
      className={className}
      onClick={handleCopyCode}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
