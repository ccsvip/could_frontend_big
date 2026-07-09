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

**Device TTS Voice Configuration**:
The current Provider Voice bound to a runtime Device, plus device-level playback controls such as speech rate, pitch, and volume. When the device voice is unbound, these playback controls are cleared and the device falls back to the Company Default TTS Voice configuration.
_Avoid_: provider voice default, global TTS settings, Android-only voice preferences

**Company User**:
A user operating inside a company workspace; company administrators and employees share the same business feature access, except that only company administrators can manage employees.
_Avoid_: tenant admin feature split, employee-only business access

**Active Company LLM Authorization**:
A platform LLM model grant that is currently enabled for a company, making that model available to that company.
_Avoid_: historical model usage, disabled authorization, chat history reference

**Third-Party Chatbot Interface**:
An externally hosted chatbot application endpoint that owns its own conversation flow and credentials, and can be made available to companies as an alternative to a platform LLM model.
_Avoid_: irregular LLM, non-standard LLM, custom LLM provider, external model

**Third-Party Chatbot Application**:
A specific externally hosted chatbot, such as a presales assistant, that carries the credentials and application identity needed for runtime conversation and can be granted to companies.
_Avoid_: third-party provider grant, external supplier, model alias

**Third-Party Chatbot Scheme**:
A platform-level reusable integration pattern for a class of Third-Party Chatbot Interfaces that share the same external API contract.
_Avoid_: irregular LLM, company one-off template, hard-coded company integration

**Third-Party Chatbot Scheme B**:
The reusable Third-Party Chatbot Scheme for FlowMesh LLM synchronous chat interfaces, where a single request sends the user question and the response contains a direct answer.
_Avoid_: workflow scheme, knowledge-base API, streaming FlowMesh integration, custom hard-coded FlowMesh adapter

**Third-Party Chatbot Scheme Instance**:
A platform-managed configuration of a Third-Party Chatbot Scheme, with its own external credentials, application identity, API flow snapshot, maintenance remark, and company grants.
_Avoid_: company-specific provider, raw API script, authorization-only record

**Company Third-Party Chatbot Grant**:
A company-specific authorization that makes a Third-Party Chatbot Application visible and selectable only within that company.
_Avoid_: global chatbot visibility, public third-party app, platform-wide external chatbot

**Device Chat Contract**:
The stable HTTP response payload and WebSocket event shape used by runtime devices for Agent Application conversations, regardless of which Agent Runtime Backend produced the answer.
_Avoid_: provider response passthrough, third-party payload contract, Android-specific third-party format

**Agent Application**:
A company-scoped LLM-backed application configured with a system prompt, knowledge documents, and runtime chat settings.
_Avoid_: 智能体, 应用, AI 应用

**Agent Runtime Backend**:
The single answer-producing backend currently active for an Agent Application, either a platform LLM model or a Third-Party Chatbot Interface; inactive backend configuration can be retained for later switching but must not affect runtime answers.
_Avoid_: mixed model source, fallback provider, simultaneous LLM binding

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

**Agent Annotation**:
A company-scoped exact-match standard reply configured on an Agent Application, used when a user question should bypass model generation and return a curated response.
_Avoid_: FAQ, knowledge item, prompt example

**Agent Reply Block**:
An ordered part of an Agent Application response, either text, image, or video; only text blocks are eligible for Agent Reply Playback.
_Avoid_: Markdown snippet, attachment, rich text fragment

**Resource Library Item**:
A company-scoped reusable image or video selected from resource management and referenced by business content such as Agent Reply Blocks.
_Avoid_: copied media file, pasted URL, attachment upload

**Agent Reply Playback**:
Text-to-speech playback of an Agent Application's opening message or assistant replies during conversation preview or runtime conversation.
_Avoid_: user input playback, suggested question playback, TTS configuration test

**Agent Voice Input**:
Speech-to-text input for an Agent Application conversation, where recorded user audio is transcribed into editable message text before the user sends it.
_Avoid_: realtime interruption, direct voice message, device ASR runtime

**Knowledge Document**:
A company-scoped document uploaded to the knowledge base and optionally bound to an Agent Application as its available reference material.
_Avoid_: dataset, knowledge collection, vector store

**Wake Word**:
A company-scoped Chinese phrase that starts with 你好, contains four to six Chinese characters including 你好, and can wake one or more runtime devices through sherpa-onnx keyword spotting.
_Avoid_: hotword, keyword, command phrase, device name

**Wake Word Keyword Line**:
The sherpa-onnx keyword spotting line generated from a Wake Word, containing the encoded token sequence, original Chinese phrase, boosting score, and trigger threshold.
_Avoid_: raw pinyin, display label, runtime-only string

**Wake Word Binding**:
The company-scoped assignment between Wake Words and Devices; each Wake Word can be assigned to multiple Devices, and each Device can have multiple Wake Words.
_Avoid_: single device wake word, application wake word, global wake word

**Knowledge Media Asset**:
A Resource Library Item bound to a Knowledge Base, and optionally later to a Knowledge Document, as supporting reference material for Agent Application answers.
_Avoid_: duplicated knowledge upload, global media match, raw media URL, manual link
