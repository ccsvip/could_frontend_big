# Component Guidelines

> How components are built and styled in this project.

---

## Component Standards

- **Icon Library**: Exclusively use `@tabler/icons-react` with `Icon` prefix (e.g., `IconDatabase`, `IconEdit`, `IconPlus`). Do not import `@ant-design/icons` or `lucide-react`.
- **Status Indicators**: Use `<StatusTag />` (`web/src/components/status-tag.tsx`) for all business status representations (`online`, `offline`, `active`, `inactive`, `bound`, `unbound`, `pending`). Avoid inline `<Tag color="...">` or custom color class strings.
- **Fluid Typography**: Use `text-fluid-*` classes defined in `web/src/styles/index.css` (`text-fluid-xs` through `text-fluid-stat`). Never use hardcoded pixel text sizes like `text-[12px]` or `text-xs`.

---

## Styling & Token Patterns

- **Color Tokens**: Use `brand-*` color palette (`text-brand-700`, `bg-brand-50`, `border-brand-200`) defined in `tailwind.config.ts`. Avoid hardcoded `#0f766e` literals or `teal-*` classes in components.
- **No `!` Override**: Never use Tailwind `!` prefix (`!p-0`, `!bg-brand-600`) to force-override Ant Design defaults. Use scoped CSS classes in `web/src/styles/index.css` when needed.
- **Pre-commit Guard**: Verified by `scripts/check-tailwind-tokens.js`. Net increase in `!` or `teal-*` classes will be blocked at commit time.

---

## Common Mistakes

- Manual inline status tags with mixed color classes across different pages.
- Mixing font scale systems (e.g. raw `text-xs` alongside `text-fluid-base`).
- Adding `!` prefix classes in TSX components to patch Ant Design styles.

---

## Convention: Agent TTS filter rules UI

**Where**: Application conversation settings (`web/src/views/application-management/index.tsx`) under reply playback.

**API fields (unchanged contract)**:
- `ttsFilterEmoji: boolean`
- `ttsFilterPunctuation: string` — visible filter chars plus optional hidden `' '` and `'\r\n'`; deduped; total length ≤ 64
- `ttsFilterExcludePatterns: string[]` — trim, dedupe, max 20, each ≤ 120

**UI projection**:
- Auto toggles: emoji / half-width space / line breaks (space & breaks are **not** separate API fields)
- Visible chars: removable chips + preset toggles (`- * # _ \` ~ > |`) + custom multi-char add
- Exclude patterns: add + delete only (no inline edit / no live filter preview panel)
- Filter block stays fully editable when reply playback is off or TTS is not ready (`canUpdate` still applies)

**Write paths**: chip remove, preset toggle, custom add, **and** space/linebreak switches must all refuse writes that would make `ttsFilterPunctuation.length > 64`, with the same user-facing warning.

**Icons**: any new Tabler icon used here must also be exported from the ambient module in `web/src/vite-env.d.ts`.
