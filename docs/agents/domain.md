# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Layout

This repo is **single-context**: one `CONTEXT.md` + `docs/adr/` at the repo root. There is no `CONTEXT-MAP.md`.

(Submodules `backend/`, `web/`, `flow-web/` carry their own `CLAUDE.md` / `AGENTS.md` for module-level FAQ, but domain language and architectural decisions are centralized at the root.)

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the project's domain language / glossary
- **`docs/adr/`** — read ADRs that touch the area you're about to work in

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-published-agent-annotations.md
│   ├── 0002-knowledge-media-assets.md
│   └── 0003-third-party-chatbots-as-separate-runtime-backends.md
├── backend/
├── web/
└── flow-web/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0002 (knowledge-media-assets) — but worth reopening because…_
