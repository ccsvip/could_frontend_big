# Solin Domain Context

This context defines product language for the Solin digital human administration platform.

## Language

**Provider Voice**:
A built-in voice option supplied by a TTS provider, identified by the provider's voice code and selected from a platform-maintained catalog.
_Avoid_: VoiceTone, voice asset, custom voice

**Platform TTS Configuration**:
The platform-owned text-to-speech provider settings used as the effective service configuration for companies and devices, with environment variables only serving as initial defaults or fallback values.
_Avoid_: company TTS credentials, frontend TTS settings

**Company Default TTS Voice**:
The provider voice selected as a company's default voice for text-to-speech synthesis and testing.
_Avoid_: tenant voice model, company voice asset

**Management TTS Test**:
A text-to-speech synthesis check performed inside the administration UI, intended for immediate browser playback.
_Avoid_: runtime synthesis, device playback

**Device TTS Runtime Audio**:
Text-to-speech audio generated for a bound runtime device, delivered as raw PCM audio with explicit audio metadata.
_Avoid_: admin preview audio, WAV test audio

**Company User**:
A user operating inside a company workspace; company administrators and employees share the same business feature access, except that only company administrators can manage employees.
_Avoid_: tenant admin feature split, employee-only business access
