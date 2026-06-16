# Agent Conversation Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Agent Application conversation settings: delete cascade behavior, opening message, suggested questions, ASR voice input, and TTS reply playback.

**Architecture:** Store conversation behavior directly on `AgentApplication`, because these settings belong to the agent and must be shared by preview, runtime, and future external entry points. Reuse existing ASR WebSocket and company TTS synthesis endpoints instead of adding provider-specific frontend logic. Keep the existing application page component, but split the detail workspace into four tabs and isolate reusable ASR/TTS helpers in small frontend utility files.

**Tech Stack:** Django 5.2 + DRF + PostgreSQL migrations, React 18 + Vite + TypeScript, Radix Themes, Ant Design message/spinner, existing WebSocket ASR and TTS HTTP APIs.

---

## File Map

- Modify `backend/apps/ai_models/models.py`
  - Add `AgentApplication` conversation setting fields.
  - Change `ChatConversation.application` deletion semantics to cascade.
- Create `backend/apps/ai_models/migrations/0017_agent_conversation_settings.py`
  - Add fields.
  - Change `application` FK to cascade.
  - Backfill default opening messages.
  - Grant `agent_applications.delete` to existing tenants and relevant roles.
- Modify `backend/apps/ai_models/serializers.py`
  - Expose and validate conversation setting fields.
- Modify `backend/apps/ai_models/tests/test_agent_application_api.py`
  - Add failing tests for defaults, validation, cascade deletion, and default delete permission.
- Modify `web/src/api/modules/applications.ts`
  - Add conversation setting fields to record and payload types.
- Reference: `web/src/api/modules/tts.ts`
  - Reuse existing `fetchCompanyTtsOptions` and `testCompanyTts` for agent playback.
- Create `web/src/views/application-management/audio-utils.ts`
  - Shared PCM encoding/downsampling helpers for ASR capture.
- Create `web/src/views/application-management/use-agent-audio.ts`
  - Encapsulate ASR recording and TTS playback state for the application page.
- Modify `web/src/views/application-management/index.tsx`
  - Add `对话设置` tab.
  - Add opening message, suggested questions, ASR input, and TTS playback UI.
  - Update delete warning.
  - Update dirty tracking and save payload.

## Task 1: Backend Conversation Setting Fields And Delete Semantics

**Files:**
- Modify: `backend/apps/ai_models/tests/test_agent_application_api.py`
- Modify: `backend/apps/ai_models/models.py`
- Create: `backend/apps/ai_models/migrations/0017_agent_conversation_settings.py`

- [ ] **Step 1: Add failing tests for defaults and cascade deletion**

Add these tests to `AgentApplicationAccessDataTests` and `AgentApplicationApiTests` in `backend/apps/ai_models/tests/test_agent_application_api.py`:

```python
    def test_seed_adds_delete_permission_to_existing_tenants(self):
        default_tenant = Tenant.objects.filter(code='default').first()

        self.assertIsNotNone(default_tenant)
        self.assertIn(
            'agent_applications.delete',
            set(default_tenant.permission_points.values_list('code', flat=True)),
        )
```

```python
    def test_create_agent_application_defaults_conversation_settings(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {'name': '样芋量'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['openingMessageEnabled'])
        self.assertEqual(
            response.data['openingMessage'],
            '你好，我是样芋量，很高兴见到你，有什么我可以帮你的吗？',
        )
        self.assertEqual(response.data['suggestedQuestions'], [])
        self.assertFalse(response.data['voiceInputEnabled'])
        self.assertFalse(response.data['replyPlaybackEnabled'])
```

```python
    def test_delete_agent_application_deletes_its_conversations_and_messages(self):
        self.grant_permissions(
            'agent_applications.view',
            'agent_applications.create',
            'agent_applications.delete',
        )
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Disposable toolbox',
        )
        document = self.create_document(title='Shared document')
        provider = self.create_provider()
        model = self.create_model(provider)
        application.knowledge_documents.set([document])
        conversation = ChatConversation.objects.create(
            user=self.user,
            application=application,
            tenant=self.tenant,
            llm_model=model,
        )
        message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.ROLE_ASSISTANT,
            content='This history belongs to the agent.',
        )

        response = self.client.delete(f'/api/v1/ai-models/applications/{application.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AgentApplication.objects.filter(id=application.id).exists())
        self.assertFalse(ChatConversation.objects.filter(id=conversation.id).exists())
        self.assertFalse(ChatMessage.objects.filter(id=message.id).exists())
        self.assertTrue(KnowledgeDocument.objects.filter(id=document.id).exists())
        self.assertTrue(LLMModel.objects.filter(id=model.id).exists())
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
```

Expected: failures because fields are missing, delete permission is not seeded, and deleting an application leaves conversations with `application_id = NULL`.

- [ ] **Step 3: Update models**

In `backend/apps/ai_models/models.py`, add helper and fields near `AgentApplication`:

```python
def default_agent_opening_message(name: str) -> str:
    agent_name = (name or '智能体').strip() or '智能体'
    return f'你好，我是{agent_name}，很高兴见到你，有什么我可以帮你的吗？'
```

Inside `AgentApplication`, after `max_tokens`:

```python
    opening_message_enabled = models.BooleanField('是否启用开场白', default=True)
    opening_message = models.TextField('开场白', blank=True, default='')
    suggested_questions = models.JSONField('建议问题', blank=True, default=list)
    voice_input_enabled = models.BooleanField('是否启用语音输入', default=False)
    reply_playback_enabled = models.BooleanField('是否自动播报回复', default=False)
```

Update `AgentApplication.save()`:

```python
    def save(self, *args, **kwargs):
        if not self.opening_message:
            self.opening_message = default_agent_opening_message(self.name)
        if self.llm_model:
            self.llm_provider = self.llm_model.provider
            self.model_name = self.llm_model.name
        else:
            self.llm_provider = None
            self.model_name = ''
        super().save(*args, **kwargs)
```

Change `ChatConversation.application`:

```python
    application = models.ForeignKey(
        AgentApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='绑定应用',
    )
```

- [ ] **Step 4: Create migration**

Create `backend/apps/ai_models/migrations/0017_agent_conversation_settings.py`:

```python
from django.db import migrations, models
import django.db.models.deletion


def default_opening_message(name: str) -> str:
    agent_name = (name or '智能体').strip() or '智能体'
    return f'你好，我是{agent_name}，很高兴见到你，有什么我可以帮你的吗？'


def backfill_agent_conversation_settings(apps, schema_editor):
    AgentApplication = apps.get_model('ai_models', 'AgentApplication')
    Tenant = apps.get_model('tenants', 'Tenant')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')

    delete_permission, _ = PermissionPoint.objects.update_or_create(
        code='agent_applications.delete',
        defaults={
            'name': '删除智能体',
            'module': 'agent_applications',
            'description': '允许删除智能体应用及其关联会话',
            'is_active': True,
        },
    )

    for tenant in Tenant.objects.all():
        tenant.permission_points.add(delete_permission)

    for role in Role.objects.all():
        if role.code == 'admin':
            role.permission_points.add(delete_permission)

    for application in AgentApplication.objects.all():
        update_fields = []
        if not application.opening_message:
            application.opening_message = default_opening_message(application.name)
            update_fields.append('opening_message')
        if application.suggested_questions is None:
            application.suggested_questions = []
            update_fields.append('suggested_questions')
        if update_fields:
            application.save(update_fields=update_fields)


def rollback_agent_conversation_settings(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    delete_permission = PermissionPoint.objects.filter(code='agent_applications.delete').first()
    if delete_permission is None:
        return
    for tenant in Tenant.objects.all():
        tenant.permission_points.remove(delete_permission)
    for role in Role.objects.all():
        role.permission_points.remove(delete_permission)


class Migration(migrations.Migration):
    dependencies = [
        ('ai_models', '0016_update_agent_application_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentapplication',
            name='opening_message_enabled',
            field=models.BooleanField(default=True, verbose_name='是否启用开场白'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='opening_message',
            field=models.TextField(blank=True, default='', verbose_name='开场白'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='suggested_questions',
            field=models.JSONField(blank=True, default=list, verbose_name='建议问题'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='voice_input_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用语音输入'),
        ),
        migrations.AddField(
            model_name='agentapplication',
            name='reply_playback_enabled',
            field=models.BooleanField(default=False, verbose_name='是否自动播报回复'),
        ),
        migrations.AlterField(
            model_name='chatconversation',
            name='application',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversations',
                to='ai_models.agentapplication',
                verbose_name='绑定应用',
            ),
        ),
        migrations.RunPython(backfill_agent_conversation_settings, rollback_agent_conversation_settings),
    ]
```

- [ ] **Step 5: Run backend tests for this task**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
```

Expected: defaults and cascade tests still fail until serializer is updated in Task 2, but migration/model errors should be gone.

- [ ] **Step 6: Commit backend model and migration**

```bash
git add backend/apps/ai_models/models.py backend/apps/ai_models/migrations/0017_agent_conversation_settings.py backend/apps/ai_models/tests/test_agent_application_api.py
git commit -m "feat: 增加智能体对话设置模型"
```

## Task 2: Backend Serializer Validation And API Contract

**Files:**
- Modify: `backend/apps/ai_models/serializers.py`
- Modify: `backend/apps/ai_models/tests/test_agent_application_api.py`

- [ ] **Step 1: Add failing serializer validation tests**

Add to `AgentApplicationApiTests`:

```python
    def test_update_agent_application_accepts_conversation_settings(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.update')
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Conversation agent',
        )

        response = self.client.patch(
            f'/api/v1/ai-models/applications/{application.id}/',
            {
                'openingMessageEnabled': True,
                'openingMessage': '你好，我是客服助手。',
                'suggestedQuestions': ['你能做什么？', '如何使用知识库？'],
                'voiceInputEnabled': True,
                'replyPlaybackEnabled': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['openingMessage'], '你好，我是客服助手。')
        self.assertEqual(response.data['suggestedQuestions'], ['你能做什么？', '如何使用知识库？'])
        self.assertTrue(response.data['voiceInputEnabled'])
        self.assertTrue(response.data['replyPlaybackEnabled'])
```

```python
    def test_suggested_questions_limit_is_ten(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Too many questions',
                'suggestedQuestions': [f'问题 {index}' for index in range(11)],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('suggestedQuestions', response.data['message'])
```

```python
    def test_suggested_questions_reject_blank_item(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Blank question',
                'suggestedQuestions': ['正常问题', '   '],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('suggestedQuestions', response.data['message'])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
```

Expected: failures because serializer does not expose or validate the new fields.

- [ ] **Step 3: Update `AgentApplicationSerializer` fields**

In `backend/apps/ai_models/serializers.py`, import the helper:

```python
from .models import (
    ASRConfig,
    ASRReplacementRule,
    AgentApplication,
    ChatConversation,
    ChatMessage,
    LLMModel,
    LLMProvider,
    LLMTestSettings,
    TTSProvider,
    TTSVoice,
    default_agent_opening_message,
)
```

Add fields inside `AgentApplicationSerializer`:

```python
    openingMessageEnabled = serializers.BooleanField(source='opening_message_enabled', required=False)
    openingMessage = serializers.CharField(source='opening_message', required=False, allow_blank=True, default='')
    suggestedQuestions = serializers.ListField(
        source='suggested_questions',
        child=serializers.CharField(max_length=120),
        required=False,
        allow_empty=True,
    )
    voiceInputEnabled = serializers.BooleanField(source='voice_input_enabled', required=False)
    replyPlaybackEnabled = serializers.BooleanField(source='reply_playback_enabled', required=False)
```

Add the fields to `Meta.fields` after `maxTokens`:

```python
            'openingMessageEnabled',
            'openingMessage',
            'suggestedQuestions',
            'voiceInputEnabled',
            'replyPlaybackEnabled',
```

Add validators:

```python
    def validate_openingMessage(self, value: str) -> str:
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError('开场白不能超过 200 字')
        return value

    def validate_suggestedQuestions(self, value: list[str]) -> list[str]:
        if len(value) > 10:
            raise serializers.ValidationError('建议问题最多 10 条')
        normalized = []
        for item in value:
            text = str(item).strip()
            if not text:
                raise serializers.ValidationError('建议问题不能为空')
            if len(text) > 120:
                raise serializers.ValidationError('单条建议问题不能超过 120 字')
            normalized.append(text)
        return normalized
```

Update `create()`:

```python
    def create(self, validated_data):
        if not validated_data.get('opening_message'):
            validated_data['opening_message'] = default_agent_opening_message(validated_data.get('name', ''))
        return super().create(validated_data)
```

- [ ] **Step 4: Run backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
```

Expected: all tests in `test_agent_application_api` pass.

- [ ] **Step 5: Commit serializer contract**

```bash
git add backend/apps/ai_models/serializers.py backend/apps/ai_models/tests/test_agent_application_api.py
git commit -m "feat: 暴露智能体对话设置接口"
```

## Task 3: Frontend API Types And Audio Helpers

**Files:**
- Modify: `web/src/api/modules/applications.ts`
- Reference: `web/src/api/modules/tts.ts`
- Create: `web/src/views/application-management/audio-utils.ts`
- Create: `web/src/views/application-management/use-agent-audio.ts`

- [ ] **Step 1: Update application API types**

In `web/src/api/modules/applications.ts`, extend `AgentApplicationRecord`:

```ts
  openingMessageEnabled: boolean;
  openingMessage: string;
  suggestedQuestions: string[];
  voiceInputEnabled: boolean;
  replyPlaybackEnabled: boolean;
```

Extend `AgentApplicationPayload`:

```ts
  openingMessageEnabled?: boolean;
  openingMessage?: string;
  suggestedQuestions?: string[];
  voiceInputEnabled?: boolean;
  replyPlaybackEnabled?: boolean;
```

- [ ] **Step 2: Confirm TTS helper is available**

`web/src/api/modules/tts.ts` already exports these helpers and should not need changes:

```ts
export const fetchCompanyTtsOptions = async () => {
  const response = await httpClient.get<CompanyTtsOptions>('/ai-models/tts/options/');
  return response.data;
};

export const testCompanyTts = async (payload: TtsTestPayload) => {
  const response = await httpClient.post<Blob>('/ai-models/tts/test/', payload, blobRequestConfig);
  return response.data;
};
```

If either export is missing in the implementation branch, add it with the exact code above.

- [ ] **Step 3: Add audio utility file**

Create `web/src/views/application-management/audio-utils.ts`:

```ts
export const downsampleBuffer = (buffer: Float32Array, inputSampleRate: number, outputSampleRate = 16000) => {
  if (outputSampleRate === inputSampleRate) {
    return buffer;
  }
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
};

export const encodePCM16 = (samples: Float32Array) => {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return buffer;
};
```

- [ ] **Step 4: Add agent audio hook**

Create `web/src/views/application-management/use-agent-audio.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { message } from 'antd';
import { buildAsrRealtimeWebSocketUrl } from '../../api/modules/asr';
import { testCompanyTts } from '../../api/modules/tts';
import { useAuthStore } from '../../store/auth';
import { downsampleBuffer, encodePCM16 } from './audio-utils';

const WORKLET_PROCESSOR = 'agent-asr-pcm-capture-processor';

type AsrPayload =
  | { type: 'asr.ready' }
  | { type: 'asr.transcript'; text: string }
  | { type: 'asr.done' }
  | { type: 'asr.error'; message?: string };

export const useAgentAudio = () => {
  const token = useAuthStore((state) => state.token);
  const tenantId = useAuthStore((state) => state.tenant?.id);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setPlayingKey(null);
    setPaused(false);
  }, []);

  const playText = useCallback(async (key: string, text: string) => {
    const normalized = text.trim();
    if (!normalized) {
      return;
    }
    if (playingKey === key && audioRef.current) {
      if (audioRef.current.paused) {
        await audioRef.current.play();
        setPaused(false);
      } else {
        audioRef.current.pause();
        setPaused(true);
      }
      return;
    }
    stopPlayback();
    try {
      const blob = await testCompanyTts({ text: normalized });
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      setPlayingKey(key);
      setPaused(false);
      audio.addEventListener('ended', stopPlayback);
      audio.addEventListener('error', () => {
        message.error('语音播放失败');
        stopPlayback();
      });
      await audio.play();
    } catch {
      message.error('语音合成失败，请检查 TTS 设置');
      stopPlayback();
    }
  }, [playingKey, stopPlayback]);

  const cleanupRecording = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
    setRecording(false);
    setTranscribing(false);
  }, []);

  const startRecording = useCallback(async (onTranscript: (text: string) => void) => {
    if (!token) {
      message.error('登录状态无效，请重新登录');
      return;
    }
    try {
      setTranscribing(true);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) {
        throw new Error('当前浏览器不支持音频采集');
      }
      const audioContext = new AudioContextClass();
      audioContextRef.current = audioContext;
      const socket = new WebSocket(buildAsrRealtimeWebSocketUrl(token, tenantId));
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as AsrPayload;
          if (payload.type === 'asr.ready') {
            setRecording(true);
            setTranscribing(false);
          }
          if (payload.type === 'asr.transcript' && payload.text) {
            onTranscript(payload.text);
          }
          if (payload.type === 'asr.done') {
            cleanupRecording();
          }
          if (payload.type === 'asr.error') {
            message.error(payload.message || 'ASR 识别失败');
            cleanupRecording();
          }
        } catch {
          message.error('ASR 返回数据解析失败');
          cleanupRecording();
        }
      };

      socket.onerror = () => {
        message.error('ASR 连接异常');
        cleanupRecording();
      };

      const source = audioContext.createMediaStreamSource(stream);
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      const workletCode = `
        class AgentAsrProcessor extends AudioWorkletProcessor {
          process(inputs) {
            const input = inputs[0];
            if (input && input[0]) {
              this.port.postMessage(input[0]);
            }
            return true;
          }
        }
        registerProcessor('${WORKLET_PROCESSOR}', AgentAsrProcessor);
      `;
      const workletUrl = URL.createObjectURL(new Blob([workletCode], { type: 'application/javascript' }));
      await audioContext.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);
      const workletNode = new AudioWorkletNode(audioContext, WORKLET_PROCESSOR);
      workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (socket.readyState !== WebSocket.OPEN) {
          return;
        }
        const pcm = encodePCM16(downsampleBuffer(event.data, audioContext.sampleRate));
        socket.send(pcm);
      };
      source.connect(workletNode);
      workletNode.connect(silentGain);
      silentGain.connect(audioContext.destination);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '无法启动语音输入');
      cleanupRecording();
    }
  }, [cleanupRecording, tenantId, token]);

  const stopRecording = useCallback(() => {
    setTranscribing(true);
    socketRef.current?.send(JSON.stringify({ type: 'asr.finish' }));
  }, []);

  useEffect(() => () => {
    cleanupRecording();
    stopPlayback();
  }, [cleanupRecording, stopPlayback]);

  return {
    recording,
    transcribing,
    playingKey,
    paused,
    playText,
    stopPlayback,
    startRecording,
    stopRecording,
  };
};
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit frontend API and helpers**

```bash
git add web/src/api/modules/applications.ts web/src/views/application-management/audio-utils.ts web/src/views/application-management/use-agent-audio.ts
git commit -m "feat: 增加智能体音频辅助能力"
```

## Task 4: Frontend Conversation Settings State And Save Payload

**Files:**
- Modify: `web/src/views/application-management/index.tsx`

- [ ] **Step 1: Add imports and active tab type**

In `web/src/views/application-management/index.tsx`, add imports:

```ts
import { fetchAsrStatus, type AsrStatusRecord } from '../../api/modules/asr';
import { fetchCompanyTtsOptions, type CompanyTtsOptions } from '../../api/modules/tts';
import { useAgentAudio } from './use-agent-audio';
```

Add icons to the `lucide-react` import:

```ts
  Mic,
  MicOff,
  Pause,
  Play,
  Square,
  Volume2,
  GripVertical,
```

Change tab state:

```ts
  const [activeTab, setActiveTab] = useState<'orchestrate' | 'conversation' | 'logs' | 'monitor'>('orchestrate');
```

- [ ] **Step 2: Add conversation setting state**

Add after existing form states:

```ts
  const [openingMessageEnabled, setOpeningMessageEnabled] = useState(true);
  const [openingMessage, setOpeningMessage] = useState('');
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [newSuggestedQuestion, setNewSuggestedQuestion] = useState('');
  const [voiceInputEnabled, setVoiceInputEnabled] = useState(false);
  const [replyPlaybackEnabled, setReplyPlaybackEnabled] = useState(false);
  const [asrStatus, setAsrStatus] = useState<AsrStatusRecord | null>(null);
  const [ttsOptions, setTtsOptions] = useState<CompanyTtsOptions | null>(null);
```

Instantiate audio hook:

```ts
  const agentAudio = useAgentAudio();
```

- [ ] **Step 3: Load settings into local state**

Inside `loadSelectedApplication`, after `setIsActive(detail.isActive);`:

```ts
      setOpeningMessageEnabled(detail.openingMessageEnabled);
      setOpeningMessage(detail.openingMessage || '');
      setSuggestedQuestions(detail.suggestedQuestions || []);
      setNewSuggestedQuestion('');
      setVoiceInputEnabled(detail.voiceInputEnabled);
      setReplyPlaybackEnabled(detail.replyPlaybackEnabled);
```

Extend `isDirty`:

```ts
    if (openingMessageEnabled !== selectedApplication.openingMessageEnabled) return true;
    if (openingMessage.trim() !== (selectedApplication.openingMessage || '')) return true;
    if (voiceInputEnabled !== selectedApplication.voiceInputEnabled) return true;
    if (replyPlaybackEnabled !== selectedApplication.replyPlaybackEnabled) return true;
    const previousQuestions = selectedApplication.suggestedQuestions || [];
    if (suggestedQuestions.length !== previousQuestions.length) return true;
    if (!previousQuestions.every((question, index) => question === suggestedQuestions[index])) return true;
```

Add the new dependencies to the `useMemo` dependency array.

- [ ] **Step 4: Load ASR and TTS status**

Add a callback:

```ts
  const loadConversationServiceStatus = useCallback(async () => {
    try {
      const [nextAsrStatus, nextTtsOptions] = await Promise.all([
        fetchAsrStatus(),
        fetchCompanyTtsOptions(),
      ]);
      setAsrStatus(nextAsrStatus);
      setTtsOptions(nextTtsOptions);
    } catch {
      message.warning('语音服务状态加载失败');
    }
  }, []);
```

Add effect:

```ts
  useEffect(() => {
    if (selectedApplicationId) {
      void loadConversationServiceStatus();
    }
  }, [loadConversationServiceStatus, selectedApplicationId]);
```

Derived flags:

```ts
  const asrReady = Boolean(asrStatus?.isActive && asrStatus.configured);
  const ttsReady = Boolean(ttsOptions?.provider.isActive && ttsOptions.defaultVoiceId);
```

- [ ] **Step 5: Include settings in save payload**

In `handleSaveConfig`, extend payload:

```ts
        openingMessageEnabled,
        openingMessage: openingMessage.trim(),
        suggestedQuestions,
        voiceInputEnabled,
        replyPlaybackEnabled,
```

Update `setSelectedApplication(updated);` remains enough for immediate state alignment. Add these dependencies to `handleSaveConfig`.

- [ ] **Step 6: Update keyboard shortcuts**

Update Alt shortcuts:

```ts
      if (e.altKey && e.key === '1') {
        e.preventDefault();
        setActiveTab('orchestrate');
      } else if (e.altKey && e.key === '2') {
        e.preventDefault();
        setActiveTab('conversation');
      } else if (e.altKey && e.key === '3') {
        e.preventDefault();
        setActiveTab('logs');
      } else if (e.altKey && e.key === '4') {
        e.preventDefault();
        setActiveTab('monitor');
      }
```

Allow save on conversation tab:

```ts
        if ((activeTab === 'orchestrate' || activeTab === 'conversation') && isDirty && canUpdate && !configSaving && !streaming) {
```

- [ ] **Step 7: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: build fails only if imports differ from existing API names; fix import names before moving on.

- [ ] **Step 8: Commit state and API wiring**

```bash
git add web/src/views/application-management/index.tsx
git commit -m "feat: 接入智能体对话设置状态"
```

## Task 5: Frontend Conversation Settings UI And Preview

**Files:**
- Modify: `web/src/views/application-management/index.tsx`

- [ ] **Step 1: Add suggested question helpers**

Add these helper functions before `renderApplicationList`:

```ts
  const addSuggestedQuestion = () => {
    const text = newSuggestedQuestion.trim();
    if (!text) {
      message.warning('请输入建议问题');
      return;
    }
    if (suggestedQuestions.length >= 10) {
      message.warning('建议问题最多 10 条');
      return;
    }
    setSuggestedQuestions((current) => [...current, text]);
    setNewSuggestedQuestion('');
  };

  const updateSuggestedQuestion = (index: number, value: string) => {
    setSuggestedQuestions((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)));
  };

  const removeSuggestedQuestion = (index: number) => {
    setSuggestedQuestions((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const moveSuggestedQuestion = (index: number, direction: -1 | 1) => {
    setSuggestedQuestions((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
  };
```

- [ ] **Step 2: Add send helper for suggested questions**

Add:

```ts
  const sendSuggestedQuestion = async (question: string) => {
    if (isDirty) {
      message.warning('请先保存对话设置，再发送建议问题');
      return;
    }
    setInputValue(question);
    const activeConversation = await ensureConversation();
    if (!activeConversation) {
      return;
    }
    setInputValue('');
    const localUserMessage: ChatMessage = {
      id: -Date.now(),
      conversationId: activeConversation.id,
      role: 'user',
      content: question,
      feedback: 'none',
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, localUserMessage]);
    setStreaming(true);
    setStreamingContent('');
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      setStreaming(false);
      abortRef.current = null;
      void refreshConversation(activeConversation.id).catch(() => {
        message.error('会话刷新失败');
      });
    };
    const controller = await sendMessageStream(
      activeConversation.id,
      question,
      true,
      null,
      (text) => setStreamingContent((current) => current + text),
      () => undefined,
      () => undefined,
      (error) => message.error(error),
      finish,
    );
    abortRef.current = controller;
  };
```

- [ ] **Step 3: Add TTS controls to assistant messages**

In `renderChatMessage`, for assistant messages add a small control below the markdown:

```tsx
              {!isUser && (
                <Flex align="center" gap="2" mt="2">
                  <Button
                    size="1"
                    variant="soft"
                    color="teal"
                    disabled={!ttsReady}
                    onClick={() => void agentAudio.playText(`message-${chatMessage.id}`, chatMessage.content)}
                  >
                    {agentAudio.playingKey === `message-${chatMessage.id}` && !agentAudio.paused ? <Pause size={12} /> : <Play size={12} />}
                    {agentAudio.playingKey === `message-${chatMessage.id}` && !agentAudio.paused ? '暂停' : '播放'}
                  </Button>
                  {agentAudio.playingKey === `message-${chatMessage.id}` && (
                    <Button size="1" variant="ghost" color="red" onClick={agentAudio.stopPlayback}>
                      <Square size={12} /> 停止
                    </Button>
                  )}
                </Flex>
              )}
```

- [ ] **Step 4: Add conversation settings tab renderer**

Add `renderConversationSettingsTab` before `renderLogsTab`:

```tsx
  const renderConversationSettingsTab = () => (
    <Grid columns={{ initial: '1', xl: 'minmax(360px, 560px) minmax(0, 1fr)' }} gap="4">
      <Flex direction="column" gap="4">
        <Card size="2">
          <Flex direction="column" gap="3">
            <Flex align="center" justify="between">
              <Box>
                <Heading size="3">开场白</Heading>
                <Text size="1" color="gray">用户进入新对话时看到的欢迎语</Text>
              </Box>
              <Switch checked={openingMessageEnabled} onCheckedChange={setOpeningMessageEnabled} disabled={!canUpdate} />
            </Flex>
            <TextArea
              value={openingMessage}
              disabled={!openingMessageEnabled || !canUpdate}
              onChange={(event) => setOpeningMessage(event.target.value.slice(0, 200))}
              rows={4}
              placeholder="输入智能体开场白"
            />
            <Flex justify="between">
              <Text size="1" color="gray">不写入聊天消息，支持播报</Text>
              <Text size="1" color="gray">{openingMessage.length}/200</Text>
            </Flex>
          </Flex>
        </Card>

        <Card size="2">
          <Flex direction="column" gap="3">
            <Flex align="center" justify="between">
              <Box>
                <Heading size="3">建议问题</Heading>
                <Text size="1" color="gray">最多 10 条，点击后直接发送</Text>
              </Box>
              <Badge color={suggestedQuestions.length >= 10 ? 'red' : 'gray'}>{suggestedQuestions.length}/10</Badge>
            </Flex>
            {suggestedQuestions.map((question, index) => (
              <Flex key={`${index}-${question}`} align="center" gap="2">
                <GripVertical size={14} className="text-slate-400" />
                <TextField.Root
                  value={question}
                  onChange={(event) => updateSuggestedQuestion(index, event.target.value.slice(0, 120))}
                  disabled={!canUpdate}
                  style={{ flex: 1 }}
                />
                <Button size="1" variant="soft" color="gray" disabled={index === 0 || !canUpdate} onClick={() => moveSuggestedQuestion(index, -1)}>
                  上移
                </Button>
                <Button size="1" variant="soft" color="gray" disabled={index === suggestedQuestions.length - 1 || !canUpdate} onClick={() => moveSuggestedQuestion(index, 1)}>
                  下移
                </Button>
                <Button size="1" variant="soft" color="red" disabled={!canUpdate} onClick={() => removeSuggestedQuestion(index)}>
                  <Trash2 size={12} />
                </Button>
              </Flex>
            ))}
            <Flex gap="2">
              <TextField.Root
                value={newSuggestedQuestion}
                onChange={(event) => setNewSuggestedQuestion(event.target.value.slice(0, 120))}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    addSuggestedQuestion();
                  }
                }}
                placeholder="添加一个建议问题，按 Enter 确认"
                disabled={!canUpdate || suggestedQuestions.length >= 10}
                style={{ flex: 1 }}
              />
              <Button disabled={!canUpdate || suggestedQuestions.length >= 10} onClick={addSuggestedQuestion}>
                <Plus size={14} /> 添加
              </Button>
            </Flex>
          </Flex>
        </Card>

        <Card size="2">
          <Flex direction="column" gap="3">
            <Flex align="center" justify="between">
              <Box>
                <Heading size="3">语音输入</Heading>
                <Text size="1" color="gray">{asrReady ? 'ASR 服务可用' : 'ASR 服务未就绪，请先检查 ASR 设置'}</Text>
              </Box>
              <Switch checked={voiceInputEnabled} onCheckedChange={setVoiceInputEnabled} disabled={!canUpdate || !asrReady} />
            </Flex>
            <Flex align="center" justify="between">
              <Box>
                <Heading size="3">回复播报</Heading>
                <Text size="1" color="gray">{ttsReady ? '使用公司默认 TTS 音色' : 'TTS 默认音色未配置或服务不可用'}</Text>
              </Box>
              <Switch checked={replyPlaybackEnabled} onCheckedChange={setReplyPlaybackEnabled} disabled={!canUpdate || !ttsReady} />
            </Flex>
          </Flex>
        </Card>
        <Button
          size="3"
          color="teal"
          disabled={!canUpdate || streaming}
          loading={configSaving}
          onClick={() => void handleSaveConfig()}
        >
          <Save size={16} /> 保存对话设置
        </Button>
      </Flex>

      <Card size="2">
        <Flex direction="column" gap="4" style={{ minHeight: 540 }}>
          <Flex align="center" justify="between">
            <Heading size="3">调试预览</Heading>
            <Badge color="blue" variant="soft">实时</Badge>
          </Flex>
          <Flex direction="column" align="center" justify="center" gap="3" style={{ flex: 1 }}>
            <Avatar size="4" fallback={<Bot size={24} />} color="teal" variant="soft" />
            <Heading size="4">开始与 {selectedApplication?.name || '智能体'} 对话</Heading>
            {openingMessageEnabled && openingMessage ? (
              <Flex direction="column" align="center" gap="2">
                <Box className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm max-w-xl">
                  <Text size="2">{openingMessage}</Text>
                </Box>
                <Button
                  size="1"
                  variant="soft"
                  color="teal"
                  disabled={!ttsReady}
                  onClick={() => void agentAudio.playText('opening-message', openingMessage)}
                >
                  {agentAudio.playingKey === 'opening-message' && !agentAudio.paused ? <Pause size={12} /> : <Volume2 size={12} />}
                  {agentAudio.playingKey === 'opening-message' && !agentAudio.paused ? '暂停开场白' : '播放开场白'}
                </Button>
              </Flex>
            ) : null}
            {suggestedQuestions.length > 0 ? (
              <Flex wrap="wrap" justify="center" gap="2">
                {suggestedQuestions.map((question) => (
                  <Button key={question} size="2" variant="soft" color="gray" disabled={streaming || !canChat} onClick={() => void sendSuggestedQuestion(question)}>
                    <HelpCircle size={14} /> {question}
                  </Button>
                ))}
              </Flex>
            ) : (
              <Text size="2" color="gray">暂无建议问题</Text>
            )}
          </Flex>
          <Flex gap="2">
            {voiceInputEnabled && (
              <Button
                size="3"
                variant="soft"
                color={agentAudio.recording ? 'red' : 'teal'}
                disabled={!asrReady || agentAudio.transcribing}
                onClick={() => {
                  if (agentAudio.recording) {
                    agentAudio.stopRecording();
                    return;
                  }
                  void agentAudio.startRecording((text) => setInputValue(text));
                }}
              >
                {agentAudio.recording ? <MicOff size={16} /> : <Mic size={16} />}
              </Button>
            )}
            <TextField.Root
              size="3"
              value={inputValue}
              placeholder="发送调试消息..."
              disabled={!canChat || streaming || !selectedApplication}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && void handleSend()}
              style={{ flex: 1 }}
            />
            <Button size="3" color="teal" disabled={!inputValue.trim() || !canChat || streaming} onClick={() => void handleSend()}>
              <Send size={16} />
            </Button>
          </Flex>
        </Flex>
      </Card>
    </Grid>
  );
```

- [ ] **Step 5: Add conversation tab navigation**

In `renderApplicationWorkspace`, add a button between `编排` and `日志与标注`:

```tsx
            <Button
              variant={activeTab === 'conversation' ? 'soft' : 'ghost'}
              color={activeTab === 'conversation' ? 'teal' : 'gray'}
              onClick={() => setActiveTab('conversation')}
              style={{ justifyContent: 'start', flex: 1, padding: '12px 16px', borderRadius: '12px' }}
            >
              <MessageSquare size={16} style={{ marginRight: 8 }} /> 对话设置
            </Button>
```

Add content branch:

```tsx
          {activeTab === 'conversation' && renderConversationSettingsTab()}
```

Change header save button condition:

```tsx
        {(activeTab === 'orchestrate' || activeTab === 'conversation') && (
```

Disable save while streaming:

```tsx
              disabled={!canUpdate || streaming}
```

- [ ] **Step 6: Update delete warning copy**

Replace delete confirmation description with:

```tsx
删除后将移除智能体配置、对话设置、关联会话和消息，且不可恢复。绑定的知识库、模型、音色和 ASR/TTS 配置不会被删除。确定删除「{app.name}」吗？
```

- [ ] **Step 7: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit UI work**

```bash
git add web/src/views/application-management/index.tsx
git commit -m "feat: 增加智能体对话设置界面"
```

## Task 6: Verification And Final Commit Audit

**Files:**
- Review all changed files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api
```

Expected: PASS for both commands.

- [ ] **Step 2: Run frontend build**

Run:

```bash
docker compose exec web npm run build
```

Expected: PASS.

- [ ] **Step 3: Run diff checks**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` prints nothing.
- `git status --short` may show the user's existing `AGENTS.md` modification; do not include it unless the user explicitly asks.

- [ ] **Step 4: Manual browser verification**

If the stack is not running, start it:

```bash
docker compose up -d
```

Open the web app at the configured host port, normally:

```text
http://localhost:5175
```

Verify:

- Create a new智能体 and see default opening message.
- Open `对话设置`.
- Add 10 suggested questions; the add control blocks the 11th.
- Save settings and see the preview update immediately.
- Click a suggested question and confirm it sends directly.
- Toggle ASR; if ASR is unavailable, the mic is disabled with a clear message.
- Click TTS playback for opening message or assistant reply; playback pauses/resumes/stops.
- Delete the agent and confirm warning copy mentions conversations/messages are deleted and shared resources are retained.

- [ ] **Step 5: Final commit if verification caused fixes**

If verification required follow-up code fixes:

```bash
git add <fixed-files>
git commit -m "fix: 完善智能体对话设置验证问题"
```

If no fixes were needed, do not create an empty commit.
