# LLM Responses API Compatibility Implementation Plan

## Ordered Work

1. Add `api_protocol` choices/default to `LLMProvider`; generate a Django migration; expose camelCase `apiProtocol` through provider read/write serializers and TypeScript API types.
2. Add the protocol selector to the platform LLM provider modal. New providers default to Chat Completions; editing pre-existing records displays their stored value.
3. Implement provider-aware URL, payload, error, text, SSE, web-search, and function-tool conversion helpers in `llm_services`.
4. Route synchronous, standard streaming, and tool streaming service functions through those helpers while preserving their existing function signatures and yielded event shapes.
5. Replace protocol-specific helpers in `views.py` chat conversation send/title/summary flow with the shared adapter; add `apiProtocol` to realtime model configuration.
6. Add focused tests for schema/API persistence, legacy compatibility, Responses non-stream/stream/tool parsing, search conversion, and command-dispatch-compatible tool events.

## Validation

- `docker compose exec backend python manage.py makemigrations --check --dry-run`
- `docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_platform_settings_api apps.ai_models.tests.test_llm_model_usage apps.ai_models.tests.test_chat_api apps.resources.tests.test_command_dispatch --keepdb`
- `npm run build` from `web/`
- Smoke test: create or edit a provider with `apiProtocol=responses`, run its connection test, then send a regular chat request; verify the captured upstream URL is `/responses` and text reaches the application SSE response.

## Review Gates

- Run GitNexus impact analysis before editing each exported/called symbol.
- Confirm no direct Chat Completions request builder remains on a path that can receive a Responses provider.
- Confirm migration default preserves existing provider records and frontend submits camelCase API fields.

## Rollback

Set a provider back to `chat_completions` through `/settings/llm/providers/{id}/` to restore the old wire protocol without changing models, grants, or conversation records. If code deployment must be reverted, revert the matching schema migration under the project migration procedure.
