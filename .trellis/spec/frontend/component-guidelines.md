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
