# Technical Design: Super-admin TTS Revocation

## Boundary

The super-admin card-authorization endpoint remains the sole write path. It accepts revocation regardless of current downstream references. Existing runtime authorization resolution, device configuration publishing, and company isolation are unchanged.

## Changes

1. Remove the serializer's card-level and voice-level “in use” validation calls and their private helper methods. Post-save default-voice validation remains: a payload that preserves an unauthorized default is still invalid.
2. Stop calculating and returning `usage`, `canDisableGrant`, and `canRevoke` in the card-authorization response because they exist solely to gate revocation.
3. Remove those API types and all UI guard/warning/disabled conditions. Keep shelf-state disables: platform-disabled cards and unlisted voices cannot be granted.
4. Replace the former blocked-revocation tests with success cases proving persisted disabled grants/ticks when default, device, and device-application references exist. Preserve the runtime event assertion already attached to a successful save.
5. Amend the TTS tenant-card authorization specification's response contract, validation matrix, and required-test list to document unconditional super-admin revocation.

## Data Flow

Super-admin page local edit → `PUT cardGrants/defaultVoiceId` → serializer derives post-save authorized voices and validates default only → transaction updates grants/ticks and default → full tenant runtime configuration event → endpoint response omits usage-based revocation gates.

## Compatibility and Risk

- No migration: grant records and write payload remain unchanged.
- The removed response keys are consumed only by the migrated in-repo page. The API is super-admin-only.
- A revoked device binding continues through the pre-existing authorization resolver; this change neither selects another card nor mutates the binding.
- Rollback is a source-only reintroduction of the removed validation and UI guards; data rows are not transformed.
