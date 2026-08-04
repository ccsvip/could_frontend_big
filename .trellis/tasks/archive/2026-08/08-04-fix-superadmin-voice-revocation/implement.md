# Implementation Plan: Super-admin TTS Revocation

1. Load backend/frontend pre-development guidance; inspect LSP references for exported API types and GitNexus impact for every modified symbol.
2. Update the serializer and authorization response builder to remove usage-based revocation enforcement and obsolete response fields, retaining default-voice validation and runtime event publishing.
3. Update API types and the super-admin authorization page so card switches and selected-mode checkboxes remain operable despite existing usage.
4. Replace blocked-revocation assertions with successful card- and voice-revocation cases; update the TTS authorization specification.
5. Run the focused Django authorization API tests in Docker and `npm run build` in `web/`; review impacted flows with GitNexus change detection before commit.

## Risky Areas

- Do not remove platform shelf-state controls. They prevent invalid grants, not revocation.
- Do not weaken `defaultVoiceId` post-save validation. The UI already clears a revoked default before it sends the request.
- Do not alter the full runtime-config publish inside the transaction.
