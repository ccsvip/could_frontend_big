# Handoff — Frontend UI Refactor (could_frontend_big)

**Session**: `ses_0e16ce8a3ffeoc9URCg2Jh1RXg` · **Date**: 2026-07-02 · **Repo**: `C:\code\company\could_frontend_big`

> Read the session notes first — they have the full detail, lessons, and gotchas. This doc is a navigation index, not a duplicate.
> **Primary artifact**: `C:\Users\cancer\.local\share\mimocode\memory\sessions\ses_0e16ce8a3ffeoc9URCg2Jh1RXg\notes.md` (turns 5, 7, 9, 11, 13)

## What the user wanted

1. "知识库 UI 不好看" → redesigned `/ai-models/knowledge-base` landing via prototype skill; user picked **variant B (master-detail)**; folded into the real page; prototype deleted.
2. "整个前端 UI 都丑，不同分辨率不一样，手机更差，不清楚问题在哪" → ran `/diagnose`; produced evidence-backed root-cause list (file:line).
3. Chose **option C (systematic refactor + update AGENTS.md)** → landed foundation + enforcement layer + mechanical migrations.

## What's DONE (all `npm run build` verified clean; nothing committed)

- **Foundation**: `.page-hero` raw `vw`→`clamp()` (12 pages benefit); `tailwind.config.ts` added `container` config + annotated `brand` as canonical scale; `AGENTS.md` (root) added a "前端设计 token 与响应式规范" section (color/`!`/responsive/mobile rules).
- **Knowledge-base landing**: rewritten to master-detail (variant B), wired to real data; `teal-*`→`brand-*`; removed a wrong `!bg-teal-600` override on a primary button.
- **Bulk `teal-*`→`brand-*`**: 13 .tsx files (zero visual change, naming compliance).
- **ConfigProvider drift**: removed nested `ConfigProvider` in `application-management/index.tsx` (was overriding `borderRadius:12` vs root `10`).
- **Responsive inputs**: 6 fixed-width toolbar inputs → mobile-first `w-full sm:w-*` (4× command-management, model-management, third-party-chatbot-settings); `!` prefix removed.
- **Icon migration — COMPLETE**: all 30 icon files migrated to `@tabler/icons-react`. 29 antd files via script (lookbehind skips string-literal contract keys); `dashboard-layout.tsx` shell done manually (menuIconMap **keys preserved** — backend `/auth/me` contract); `application-management` lucide→tabler (dropped redundant `ChevronDown as ChevronDownIcon` alias). `0` `@ant-design/icons`/`lucide-react` imports remain. Added CSS shim `.anticon > svg{width:1em;height:1em}` so tabler SVGs scale in antd Button/Menu wrappers.
- **Pre-commit guard (FOLLOWUP #6) — DONE**: `scripts/check-tailwind-tokens.js` + `.githooks/pre-commit`, activated via `git config core.hooksPath .githooks`. **Net-count design**: blocks iff a staged .tsx's `!`-count or `teal-*`-count *increases* vs HEAD (refactors that keep counts flat pass; pure new additions block). Tested: bad file → exit 1; current migration → exit 0.

## Current git state

**39 files staged, NOTHING committed.** Staged set = the guard files (`.githooks/pre-commit`, `scripts/check-tailwind-tokens.js`) + `AGENTS.md` + `web/tailwind.config.ts` + `web/src/styles/index.css` + 35 .tsx files (icon migration + teal rename + knowledge-base landing rewrite + responsive inputs + ConfigProvider removal). `core.hooksPath=.githooks` is set locally.

**Important**: the pre-commit guard runs on commit. The staged migration passes it (verified — net `!`/teal counts flat-or-down). But the guard files themselves are staged with default perms — on unix clones the hook needs `chmod +x .githooks/pre-commit` (documented in AGENTS.md).

## What's LEFT (only one real item + one optional)

1. **FOLLOWUP #2 — `!`-purge (~534 existing overrides) — BLOCKED on browser.** This is the ONLY remaining substantive item. Cannot be done blind: `!p-0`/`!m-0`/`!border` etc. exist to suppress antd defaults; blind removal re-adds padding/borders and breaks layouts. Needs a visual feedback loop (dev server + human eyes, or headless browser with auth). The pre-commit guard now **freezes** these at current count — they can't grow, but the存量 stays until a browser pass. Per-file cleanup order (worst first): knowledge-base (~115), application-management (~107), device-management (~33), resource-management (~32), command-management/workspace (~26), model-management (~24).
2. **Optional — CI mode for the guard.** Current `check-tailwind-tokens.js` only checks staged files. A CI mode would scan all `*.tsx` HEAD-vs-worktree. Not built. Low priority now that the pre-commit guard exists.

## Critical lessons / gotchas (see notes.md turn 11 & 13 for full detail)

- **Never inline `(?<!['"])` regex in a pwsh `-command`** — quote mangling produced an invalid regex → `-replace` returned null → `WriteAllText($null)` **emptied `asr-settings/index.tsx`**. Restored via `git checkout --`. Always use a `.ps1` file run via `pwsh -File`.
- **Lookbehind-for-quote is insufficient for English-word icon names** (lucide `User`/`Bot`/`Plus`): it only checks string *start*, not *middle*. `User` inside a systemPrompt string got renamed to `IconUser` ("help the IconUser practice") — caught by grep `'[^']*Icon[A-Z][a-z]`, fixed manually. For future icon-lib migrations, rename only `<LucideName` (JSX opening) + import block, never bare identifiers.
- **`$LASTEXITCODE` after a pipe** (`node ... | Select-Object`) reflects the pipe's last command, not node. Use `$out = node ... 2>&1; $code = $LASTEXITCODE`.
- **`JSON.stringify(path)` in `git show :path`** produced `::"path"` → silent failure → guard no-op. Use `show "${rev}:${file}"`.

## Suggested skills (invoke via Skill tool)

- **`diagnose`** — already used for the UI audit; the diagnosis (Phase 1 feedback loop = static scan) is in notes.md turn 5. Re-invoke only if revisiting the `!`-purge with a browser loop (Phase 1 would then be headless screenshots at 375/768/1280/1920px).
- **`setup-pre-commit`** — if the team wants the FULL Husky+lint-staged+Prettier+typecheck stack instead of the lightweight `.githooks/` dir I built. Currently using the dependency-free committed-hooks approach; this skill would replace it with the standard Husky setup.
- **`code-review`** — before committing the 39 staged files, run a review of the diff. The icon migration touched 30 files and had one string-corruption regression (caught+fixed); a review pass would surface any I missed.
- **`ship`** — when the user is ready to commit/PR the staged changes. The pre-commit guard will run automatically.
- **`design-review`** or **`impeccable`** — for the eventual `!`-purge / visual polish pass once a browser is available. These need a running dev server + auth.

## Quick-start for the next agent

1. Read `notes.md` (path above) — turns 5/7/9/11/13 have everything.
2. Read `AGENTS.md` "前端设计 token 与响应式规范" + "Pre-commit 设计 token 守卫" sections for the rules now in force.
3. `cd web && npm run build` to confirm clean state (~10s).
4. To resume `!`-purge: get a browser loop first. Start `docker compose up -d` (backend) + `cd web && npm run dev`, login, then clean file-by-file (knowledge-base first), verifying each in browser. The pre-commit guard ensures no backsliding during the cleanup.
5. Do NOT commit unless the user explicitly asks. If asked, the guard passes on the current staged set.
