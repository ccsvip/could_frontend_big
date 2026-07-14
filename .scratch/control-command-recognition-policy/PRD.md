# 控制指令识别策略
Status: ready-for-agent

## Problem Statement

控制指令在 ASR 完成或文本输入进入实时会话后，目前使用固定的本地匹配规则决定直接执行或交由 LLM Tool Calling 确认。Company User 无法根据本公司控制指令的名称相似度、ASR 误识别情况和现场风险调整该规则；同时，低置信候选在 LLM 不可用、超时或未选择工具时可能退回普通对话，控制行为不够清晰、可控和可审计。

Company User 需要在指令管理中为本公司配置一套只作用于 Control Command 的识别策略，并清楚看到每次会话采用的分数、分流结果和执行结果。该策略不得混淆为 ASR 或 LLM 的置信度，也不得改变 Task Command 或普通 Agent Application 对话的既有语义。

## Solution

引入公司级的 Control Command Recognition Policy。该策略使用现有本地规则计算出的 Control Command Match Confidence，将控制指令候选分为直接执行、LLM 二次确认和普通对话三个区间。

Company User 在“指令管理 → 控制指令”顶部编辑两个阈值，保存后立即对后续请求生效，并可恢复默认值。运行时始终只读取当前公司启用的 Control Command；高置信且无歧义的命令保持异步本地执行，中等置信命令只向 LLM 提供有限候选以作确认，低置信文本保持普通对话。中等置信命令未被确认时默认不执行，并给出明确提示。

## User Stories

1. As a Company User, I want to configure a Control Command Recognition Policy for my company, so that local control behavior matches my devices and voice environment.
2. As a Company User, I want to set a direct-execution threshold, so that only sufficiently reliable Control Command Match Confidence scores can trigger a device action without LLM confirmation.
3. As a Company User, I want to set an LLM-confirmation threshold, so that borderline control phrasing can receive a limited semantic confirmation rather than being executed immediately.
4. As a Company User, I want the policy editor to explain the three score ranges before I save, so that I understand the effect of each threshold.
5. As a Company User, I want invalid threshold combinations rejected with a clear validation message, so that no unsafe or impossible policy can be saved.
6. As a Company User, I want to restore the standard `0.90 / 0.70` thresholds, so that experimentation can be reversed quickly.
7. As a Company User, I want saved changes to affect later requests immediately, so that I do not need to restart a device, Docker service, or WebSocket connection.
8. As a runtime device user, I want a high-confidence, unambiguous control phrase to execute without waiting for an upstream LLM, so that device control is fast and predictable.
9. As a runtime device user, I want a medium-confidence control phrase to be checked before execution, so that similar device commands are not executed by mistake.
10. As a runtime device user, I want an unconfirmed, timed-out, or unavailable LLM confirmation to leave devices unchanged and ask me to repeat, so that uncertain voice input is safe.
11. As a runtime device user, I want low-confidence text to remain an ordinary Agent Application conversation, so that normal questions do not become failed control attempts.
12. As a Company User, I want voice-derived and directly entered text to follow the same Control Command Recognition Policy, so that the same phrase does not behave differently by input channel.
13. As a Company User, I want only my company's active Control Commands considered, so that threshold tuning cannot disclose or execute another company's commands.
14. As a Company User, I want Task Commands to retain their existing behavior, so that a Control Command safety setting does not unexpectedly alter task orchestration.
15. As a Company User, I want to see the highest and second-highest match scores, the selected path, and the final execution outcome in device chat history, so that I can tune the policy from evidence.
16. As a runtime client, I want the existing completion event to expose structured command-dispatch diagnostics, so that clients can display or record recognition decisions without parsing speech text.
17. As a platform maintainer, I want diagnostic data to omit command transport endpoints, credentials, and raw sensitive tool arguments, so that observability does not weaken operational security.
18. As a platform maintainer, I want all command execution and database access to remain asynchronous at the existing boundaries, so that threshold evaluation does not block concurrent realtime sessions.

## Implementation Decisions

- Introduce a tenant-scoped singleton Control Command Recognition Policy. It stores `directExecutionThreshold` and `llmConfirmationThreshold` as decimal values, with defaults of `0.90` and `0.70` for every company.
- Expose the policy through the existing tenant-scoped REST API conventions. The request and response use camelCase `directExecutionThreshold` and `llmConfirmationThreshold`; the current company is derived from the authenticated tenant scope and cannot be supplied by an ordinary Company User.
- Enforce `0.90 <= directExecutionThreshold <= 1.00`, `0.50 <= llmConfirmationThreshold <= directExecutionThreshold`, and two decimal places. The first and second candidate scores must remain separated by at least `0.10` before direct execution; this safety margin is fixed and not configurable.
- Place the editor at the top of the Control Command management view. It uses precise numeric controls, visibly explains the three ranges, has an explicit save action, shows the currently effective values, and provides a restore-default action.
- Control Command Match Confidence remains a deterministic local score derived from normalized command name and command code comparison. It is not ASR confidence, LLM confidence, or a semantic probability.
- Apply ASR replacement rules and filler-word filtering before Control Command Match Confidence is calculated for voice input. Apply the same recognition policy to direct text that enters the realtime command-dispatch flow.
- For active Control Commands only, score at or above the direct-execution threshold with the required margin directly invokes the existing asynchronous control executor. No LLM request is made for that path.
- A Control Command score at or above the LLM-confirmation threshold but below the direct-execution threshold, or lacking the required margin, passes only the bounded control candidates to the existing LLM Tool Calling confirmation path.
- A top Control Command score below the LLM-confirmation threshold is not a control candidate and continues as ordinary Agent Application conversation. Task Commands retain their existing selection and execution behavior.
- When bounded LLM confirmation is unavailable, times out, fails, or returns no selected Control Command, do not execute a control action and do not fall back to ordinary LLM conversation. Return a concise repeat-request prompt suitable for voice playback.
- Read the current company's policy for every dispatch attempt through the existing asynchronous database boundary. Saving a policy affects later requests immediately; in-flight dispatches retain the policy already read for that request.
- Extend the existing optional command-dispatch completion payload and the persisted Device Runtime Conversation/chat record with safe diagnostics: highest score, second-highest score, candidate count, selected route, confirmation outcome, and execution outcome. Preserve the existing event sequence and omit host, port, credentials, and raw tool arguments.
- Keep the unified WebSocket endpoint and Device Chat Contract. No new business WebSocket path, separate ASR endpoint, or client-side command execution is introduced.
- Company administrators and employees retain the repository's established equivalent business permissions. Tenant scoping remains centralized; ordinary company users cannot read or modify another company's policy or diagnostics.

## Testing Decisions

- The main test seam is one external, end-to-end scenario: save the current company's policy through the tenant-scoped REST configuration contract, then initiate a device conversation through the existing unified WebSocket. Assert externally visible dispatch events, speech-ready responses, persisted diagnostics, and device execution calls rather than private helper calls or task internals.
- Reuse the existing realtime command-dispatch and fast-command-dispatch tests as prior art for WebSocket event ordering, bounded Tool Calling, asynchronous control execution, and tenant isolation. Reuse existing control-command API tests as prior art for REST serialization, validation, and permissions.
- Verify direct execution at `0.90` or above with a score lead of at least `0.10`, asserting no LLM confirmation call and one asynchronous control execution.
- Verify a score in the configured confirmation band, asserting that only bounded Control Command candidates are passed to LLM confirmation and that execution occurs only when the LLM selects a candidate.
- Verify an ambiguous high score whose lead is below `0.10`, asserting it enters confirmation rather than direct execution.
- Verify a low score, asserting ordinary conversation behavior and no control execution.
- Verify missing LLM configuration, timeout, upstream failure, and no-tool responses for the confirmation band, asserting no device action, no ordinary-chat fallback, and a stable repeat-request response.
- Verify policy validation at both numeric boundaries, invalid ordering, excessive precision, defaults, restore-default behavior, immediate effect on a subsequent request, and tenant isolation for read and update operations.
- Verify ASR-replaced input and direct text input produce the same policy decision for equivalent normalized text.
- Verify Task Command scenarios preserve their existing behavior and are not reclassified by the Control Command Recognition Policy.
- Verify `llm.done.commandDispatch` and persisted diagnostics contain the agreed score and route fields without sensitive network or tool data.
- Run Django tests in the Docker Compose backend container with `--keepdb`; run the frontend production build after the management UI and API types change.

## Out of Scope

- Replacing the current deterministic scoring algorithm with vector similarity, a trained classifier, an ASR confidence score, or a new LLM scoring service.
- Editing individual Control Command names, command codes, transport protocols, hosts, ports, or payload encoding as part of policy configuration.
- Changing Task Command matching, task step orchestration, Third-Party Chatbot Interface behavior, or normal Agent Application conversation beyond the explicitly defined low-score route.
- Adding a second WebSocket, a separate device authentication mechanism, client-side UDP/TCP execution, or a Docker restart requirement.
- Making the fixed `0.10` candidate-separation safety margin configurable.
- Retaining raw ASR audio, exposing credentials, or exposing control transport details in diagnostics.

## Further Notes

- The policy is a company-level operational setting, not a property of an individual Control Command. The custom execution reply and reply strategy already configured on a Control Command continue to determine the response after a successful execution.
- The recognized route should use stable machine-readable values in API and WebSocket payloads while the management UI renders localized labels.
- Existing companies receive the default policy without manual migration work; no runtime restart is required after a policy update.
