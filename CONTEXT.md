# Solin Domain Context

This context defines product language for the Solin digital human administration platform.

## Language

**Provider Voice**:
A built-in voice option supplied by a TTS provider, identified by the provider's voice code and selected from a platform-maintained catalog.
_Avoid_: VoiceTone, voice asset, custom voice

**TTS Provider**:
A platform-level text-to-speech service option, such as Aliyun, that owns a Provider Voice catalog and the credentials used for synthesis.
_Avoid_: custom voice, voice asset, tenant voice

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

**Active Company LLM Authorization**:
A platform LLM model grant that is currently enabled for a company, making that model available to that company.
_Avoid_: historical model usage, disabled authorization, chat history reference

**Agent Application**:
A company-scoped LLM-backed application configured with a system prompt, knowledge documents, and runtime chat settings.
_Avoid_: 智能体, 应用, AI 应用

**Agent Conversation Settings**:
Runtime conversation behavior configured on an Agent Application, including its opening message, suggested questions, voice input, and reply playback.
_Avoid_: device settings, user preferences, prompt variables

**Agent Application Conversation**:
A conversation that belongs to an Agent Application and is removed when that Agent Application is deleted.
_Avoid_: standalone chat, retained history, shared log

**Agent Opening Message**:
A greeting configured on an Agent Application and shown when a user starts a new conversation with that application.
_Avoid_: system prompt, first assistant answer, default reply

**Agent Suggested Question**:
A curated starter question configured on an Agent Application and shown near the opening message; an Agent Application can have up to ten suggested questions.
_Avoid_: FAQ, knowledge question, prompt variable

**Agent Reply Playback**:
Text-to-speech playback of an Agent Application's opening message or assistant replies during conversation preview or runtime conversation.
_Avoid_: user input playback, suggested question playback, TTS configuration test

**Agent Voice Input**:
Speech-to-text input for an Agent Application conversation, where recorded user audio is transcribed into editable message text before the user sends it.
_Avoid_: realtime interruption, direct voice message, device ASR runtime

**Knowledge Document**:
A company-scoped document uploaded to the knowledge base and optionally bound to an Agent Application as its available reference material.
_Avoid_: dataset, knowledge collection, vector store
