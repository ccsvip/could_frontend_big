# LLM Responses API Compatibility Design

## Boundary

`LLMProvider.api_protocol` is the single source of truth for the upstream protocol of all models owned by a provider.

- `chat_completions` is the database and serializer default, preserving every existing provider record.
- `responses` selects the OpenAI Responses-compatible endpoint.
- Provider type remains a display/category field; it does not select the wire protocol.

The platform-provider REST resource exposes this as `apiProtocol`. The `/settings/llm` provider form presents a required protocol select. No tenant-facing API or WebSocket contract changes.

## Protocol Adapter

Move protocol-specific details behind `llm_services` helpers used by all LLM call paths:

| Concern | Chat Completions | Responses |
| --- | --- | --- |
| URL | normalize to `/chat/completions` | normalize to `/responses` |
| text request | `messages`, `max_tokens` | `input`, `max_output_tokens` |
| web search | existing `enable_search` and `search_options` | append the standard `web_search` Responses tool |
| function schemas | existing `{type: function, function: {...}}` | flatten to `{type: function, name, description, parameters}` |
| text response | `choices[0].message.content` | `output[].content[]` `output_text` |
| stream delta | `choices[0].delta.content` | `response.output_text.delta` event `delta` |
| function call | streamed `delta.tool_calls` | completed `function_call` output item, converted to the existing `{id, type, function}` shape |

The adapter preserves the public Python caller contracts: text functions return strings; stream functions yield text; tool streams yield `delta`, `tool_calls`, and `done` event dictionaries. It accepts provider/model configuration so device realtime dispatch continues to avoid serializing credentials to clients.

## Call Paths

1. `run_llm_chat_completion` and `run_llm_model_test` use the adapter for synchronous non-stream calls.
2. `stream_llm_chat_completion` and `stream_llm_chat_completion_with_tools` use the adapter for realtime/device streaming and resource command dispatch.
3. Chat conversation send, title generation, and summary generation replace their duplicated Chat Completions URL/payload/parser helpers with the adapter. This prevents the page path from bypassing the selected protocol.
4. `config.realtime._prepare_device_llm_session` adds `apiProtocol` to its private `modelConfig` so it reaches the streaming adapter.

## Migration and Rollback

Add a non-null provider column with default `chat_completions`; existing records require no data migration and retain their exact wire behavior. Rolling back the code requires rolling back the schema migration first or retaining a tolerant model definition; deploy the migration together with the code.

## Error Handling

Retain the existing HTTP status, timeout, and OpenAI-compatible `error.message` handling. Add Responses error-event handling in stream parsing. Unknown event types and malformed output items are ignored; a completed response with no text remains an empty-response error at the existing caller boundary.

## Risks

- Responses API event and tool representations differ from Chat Completions; tests must assert adaptation rather than raw upstream implementation details.
- The Responses standard web search tool may not be implemented by every third-party compatibility endpoint. The provider-level explicit protocol selection makes this provider configuration failure visible through the existing connection test; no silent fallback to Chat Completions is allowed.
