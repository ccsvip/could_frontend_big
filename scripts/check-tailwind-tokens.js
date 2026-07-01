#!/usr/bin/env node
/**
 * Pre-commit guard for the frontend design-token rules (see AGENTS.md → "前端设计 token 与响应式规范").
 *
 * Design: NET-COUNT enforcement. For each staged *.tsx, compare the count of `!`-prefixed
 * Tailwind classes and `teal-*` classes between HEAD (old) and the staged version (new).
 *   • Block if a file's `!`-count INCREASES (new regressions). Refactors that keep the count
 *     flat or reduce it (e.g. icon migration, teal→brand rename) pass cleanly.
 *   • Block if `teal-*` count INCREASES (any new teal is a violation; the codebase is teal-free).
 *
 * This avoids false-positives on lines merely touched during unrelated refactors, while still
 * preventing total `!`/teal usage from growing. Bypass: `git commit --no-verify`.
 * Deps: none — Node built-ins only.
 */
const { execSync } = require('node:child_process');
const path = require('node:path');

const BAD_BANG = /![a-z][a-z0-9]*(?:-[a-z0-9]+)+/g; // hyphenated !-class (!p-0, !bg-brand-600). JS !var has no hyphen → not matched.
const BAD_TEAL = /\bteal-\d/g; // teal-600 etc.
const ROOT = path.resolve(__dirname, '..');

const run = (args) => execSync(`git ${args}`, { cwd: ROOT, encoding: 'utf8' });

function stagedTsxFiles() {
  return run('diff --cached --name-only --diff-filter=ACM')
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s && s.endsWith('.tsx'));
}

// Returns file content at a git revision (HEAD: = committed, : = staged/index). '' if absent.
function cat(file, rev) {
  try {
    return run(`show "${rev}:${file}"`);
  } catch {
    return ''; // new file (no HEAD) or deleted — treat as empty.
  }
}

function counts(content) {
  return {
    bang: (content.match(BAD_BANG) || []).length,
    teal: (content.match(BAD_TEAL) || []).length,
  };
}

function main() {
  const files = stagedTsxFiles();
  if (!files.length) process.exit(0);
  const lines = [];
  let blocked = false;
  for (const f of files) {
    const oldC = counts(cat(f, 'HEAD'));
    const newC = counts(cat(f, ''));
    const bangDelta = newC.bang - oldC.bang;
    const tealDelta = newC.teal - oldC.teal;
    if (bangDelta > 0 || tealDelta > 0) {
      blocked = true;
      lines.push(`  ${f}  →  ! 前缀: ${oldC.bang} → ${newC.bang} (+${bangDelta})  ·  teal-*: ${oldC.teal} → ${newC.teal} (+${tealDelta})`);
    }
  }
  if (!blocked) process.exit(0);
  console.error('\n❌ Pre-commit 设计 token 守卫拦截：检测到禁用样式净增量\n');
  console.error('禁用规则（见 AGENTS.md → 前端设计 token 与响应式规范）：');
  console.error('  • Tailwind `!` 前缀覆盖（!p-0、!bg-brand-600、!rounded-xl）不得新增 — 改用 antd token 默认或 styles/index.css 的作用域全局类');
  console.error('  • `teal-*` 色阶不得新增 — 改用 `brand-*`（tailwind.config.ts 定义）\n');
  console.error('以下文件的 `!`/teal 计数较 HEAD 上升（仅拦截净增量，存量不触发）：');
  console.error(lines.join('\n'));
  console.error('\n请把新增的 `!`/teal 改成合规写法后再提交。紧急情况可用 `git commit --no-verify` 跳过，但请在 AGENTS.md 记录原因。\n');
  process.exit(1);
}

main();
