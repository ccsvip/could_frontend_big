---
target: web/src/views/application-management/index.tsx
total_score: 29
p0_count: 0
p1_count: 2
timestamp: 2026-06-16T03-06-58Z
slug: web-src-views-application-management-index-tsx
---
# Design Critique: Agent Application Studio

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Missing warning/indicator for unsaved form edits. |
| 2 | Match System / Real World | 4 | Domain terminology matches industry standard (System Prompt, Temperature, etc.). |
| 3 | User Control and Freedom | 3 | Exits and stop-streaming options exist; no quick "revert changes" function. |
| 4 | Consistency and Standards | 3 | Selection bar uses banned side-stripe border (`border-l-4`). Icon hover text-on-color contrast is low. |
| 5 | Error Prevention | 3 | Model selector correctly disabled when empty; validation on text inputs could be stricter. |
| 6 | Recognition Rather Than Recall | 3 | Chat preview lacks indicators of the currently applied prompt/model under test. |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts for tab navigation, debugging actions, or document bulk selection. |
| 8 | Aesthetic and Minimalist Design | 3 | Color palette is clean and functional, but some toolbar cards have minor styling inconsistency. |
| 9 | Error Recovery | 3 | Generic API error alerts are shown; validation details from backend could be clearer. |
| 10| Help and Documentation | 2 | Missing inline tooltips or help icons for complex LLM options (e.g. Temperature). |
| **Total** | | **29/40** | **Good** |

## Anti-Patterns Verdict

- **LLM Assessment**: The page uses a very clean slate-and-teal theme aligned with the project's brand personality. However, it still exhibits two minor slop tells: the use of a side-stripe accent border to indicate active status in lists, and a color contrast failure on hover for key icons.
- **Deterministic Scan**: The static analysis scan identified two specific issues in `C:\SVN_CODE\branches\real\could_frontend\web\src\views\application-management\index.tsx`:
  - `side-tab` (line 924): Use of `border-l-4` for active list items.
  - `gray-on-color` (line 529): Text color `text-slate-500` remains active on `bg-teal-600` background inside a hover action, violating WCAG contrast standards.

## Overall Impression

The interface presents a highly professional, dense, and task-focused layout suitable for digital human management. The main opportunity is to move from a standard template feel to a polished tool by resolving visual bugs, improving a11y contrast, and adding tooltips / keyboard shortcuts.

## What's Working

1. **Structured Layout**: Splitting the screen into a configuration column and a live debugging workspace reduces cognitive load during iteration.
2. **Model Availability Safeguards**: Automatically disabling the model select when no provider has active models prevents users from saving non-functional configs.
3. **Clean Tab Navigation**: The vertical side tabs provide clear access to Orchestrate, Logs, and Monitor views.

## Priority Issues

### [P1] Banned side-stripe border on active conversation log items
- **Why it matters**: It violates the visual guidelines banning decorative side borders and marks the UI as AI-scaffolded.
- **Fix**: Remove `border-l-4 border-teal-500`. Highlight the active conversation using a background tint like `bg-teal-50/60` and a full border highlight or a distinct visual state indicator.
- **Suggested command**: `$impeccable polish`

### [P1] Low contrast icon text on hover for Create Agent card
- **Why it matters**: Hitting hover states turns the background teal but leaves the icon gray, causing low contrast (under 2:1), which violates WCAG compliance.
- **Fix**: Add `group-hover:text-white` or `group-hover:text-teal-50` to the icon wrapper.
- **Suggested command**: `$impeccable polish`

### [P2] Lack of warning for unsaved changes
- **Why it matters**: Users changing system prompts or configuration values might lose their edits if they click away or switch tabs without clicking the save button.
- **Fix**: Set a dirty state flag when config fields differ from the selected application details and show an unsaved badge next to the save button, or warn before unloading.
- **Suggested command**: `$impeccable polish`

### [P2] Missing inline help / tooltips for configuration parameters
- **Why it matters**: Non-technical tenant admins may not understand terms like "随机性温度 (Temperature)" or "系统提示词 (System Prompt)", leading to confusion.
- **Fix**: Add a small info icon next to these headers that opens a Radix UI tooltip or popover with explanations.
- **Suggested command**: `$impeccable clarify`

### [P3] Absence of keyboard accelerators for power users
- **Why it matters**: Developer workflows are slowed down by having to mouse-click the Send button or click tabs.
- **Fix**: Add basic shortcuts (e.g., Ctrl+Enter in inputs, Esc to close dialogs, Alt+1/2/3 to switch tabs).
- **Suggested command**: `$impeccable polish`

## Persona Red Flags

- **Jordan (First-Timer)**: Jordan lands on the Orchestrate panel. They see "System Prompt" and "Temperature" but have no context or templates to understand how these inputs change the agent's behavior. Jordan faces high confusion and has to search for external docs.
- **Alex (Power User)**: Alex wants to test multiple configurations rapidly. There is no quick shortcut to clear/reset the debug conversation, and no hotkeys to toggle between the configuration view and the monitor charts.

## Minor Observations

- The pagination buttons at the bottom of the list are very basic and lack page-jump features.
- The system prompt text area does not auto-resize to fit large prompt text, requiring vertical scrolling.

## Questions to Consider

- Should we display the current active prompt/model version inside the chat history as a system message to aid debugging?
- Can we provide pre-configured system prompt templates (e.g., "Customer Service", "Technical Assistant") for first-time users?
