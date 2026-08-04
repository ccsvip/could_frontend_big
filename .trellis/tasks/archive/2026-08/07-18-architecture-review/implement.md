# 架构问题排查 Implement Plan

## Checklist

1. Load planning and architecture-review context.
2. Read domain context and ADRs.
3. Use CodeGraph to locate architecture hotspots across backend, frontend, and cross-layer flows.
4. Read source for candidate areas and record concrete file anchors.
5. Select at least 3 high-signal candidates.
6. Generate self-contained HTML report in OS temp directory.
7. Open or provide the absolute report path.
8. Summarize top recommendation and ask which candidate to explore next.

## Validation

- Confirm the HTML file exists at the generated temp path.
- Confirm the report includes at least 3 candidate cards and a Top recommendation section.
- Confirm no business source files were modified.

## Risky Areas To Inspect

- Device Runtime configuration and unified WebSocket routing.
- Agent Application chat flow and Agent Runtime Backend switching.
- Third-Party Chatbot Scheme / Scheme Instance / grant model.
- Company-scoped TTS and ASR settings.
- Frontend API modules and page-level business logic duplication.

## Notes

- Codex inline mode: do not dispatch sub-agents.
- Do not start code refactoring inside this task.
