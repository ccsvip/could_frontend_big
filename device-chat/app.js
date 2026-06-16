(function () {
  'use strict';

  const DEFAULT_CONFIG = {
    API_BASE_URL: location.protocol === 'file:' ? 'http://localhost:8880/api/v1' : `${location.origin}/api/v1`,
    DEVICE_CODE_QUERY_KEY: 'deviceCode',
    DEVICE_CODE_HEADER: 'X-Device-Code',
    ACTIVATE_PATH: '/device-auth/activate/',
    SESSION_PATH: '/device-runtime/config/',
    VOICE_CHAT_PATH: '/device/voice-chat',
    ASR_REALTIME_PATH: '/ws/asr/test/',
    MAX_RECORD_SECONDS: 60,
    PCM_SAMPLE_RATE: 16000,
    MIN_RECORD_MS: 700,
    REQUEST_TIMEOUT: 30000,
    ASR_FINISH_TIMEOUT: 5000,
    ASR_PENDING_CHUNK_LIMIT: 80,
    AUTO_PLAY_AUDIO: true,
  };

  const query = new URLSearchParams(location.search);
  const CONFIG = {
    ...DEFAULT_CONFIG,
    ...(window.DEVICE_CHAT_CONFIG || {}),
  };
  CONFIG.API_BASE_URL = query.get('apiBaseUrl') || CONFIG.API_BASE_URL;
  CONFIG.ACTIVATE_PATH = query.get('activatePath') || CONFIG.ACTIVATE_PATH;
  CONFIG.SESSION_PATH = query.get('sessionPath') || CONFIG.SESSION_PATH;
  CONFIG.VOICE_CHAT_PATH = query.get('voiceChatPath') || CONFIG.VOICE_CHAT_PATH;
  CONFIG.ASR_REALTIME_PATH = query.get('asrRealtimePath') || CONFIG.ASR_REALTIME_PATH;

  const els = {
    globalStatus: document.getElementById('globalStatus'),
    globalStatusText: document.getElementById('globalStatusText'),
    connectForm: document.getElementById('connectForm'),
    deviceCodeInput: document.getElementById('deviceCodeInput'),
    apiBaseInput: document.getElementById('apiBaseInput'),
    connectButton: document.getElementById('connectButton'),
    resetButton: document.getElementById('resetButton'),
    recordButton: document.getElementById('recordButton'),
    recordButtonText: document.getElementById('recordButtonText'),
    recorderStage: document.getElementById('recorderStage'),
    retryButton: document.getElementById('retryButton'),
    clearButton: document.getElementById('clearButton'),
    noticeBox: document.getElementById('noticeBox'),
    recordingTime: document.getElementById('recordingTime'),
    deviceNameText: document.getElementById('deviceNameText'),
    deviceStateText: document.getElementById('deviceStateText'),
    applicationText: document.getElementById('applicationText'),
    sessionIdText: document.getElementById('sessionIdText'),
    traceIdText: document.getElementById('traceIdText'),
    questionText: document.getElementById('questionText'),
    answerText: document.getElementById('answerText'),
    questionCount: document.getElementById('questionCount'),
    answerCount: document.getElementById('answerCount'),
    answerAudio: document.getElementById('answerAudio'),
    playButton: document.getElementById('playButton'),
  };

  const state = {
    deviceCode: '',
    device: null,
    sessionId: '',
    mediaStream: null,
    audioContext: null,
    audioSource: null,
    audioProcessor: null,
    audioGain: null,
    asrSocket: null,
    asrFinishTimer: 0,
    asrLiveText: '',
    asrFinalText: '',
    asrPendingBuffers: [],
    pcmChunks: [],
    recordingStartedAt: 0,
    recordingTimer: 0,
    maxRecordTimer: 0,
    lastAudioBlob: null,
    lastAudioFormat: '',
    phase: 'idle',
    discardRecording: false,
    recordingStopPending: false,
  };

  function init() {
    const urlDeviceCode = query.get(CONFIG.DEVICE_CODE_QUERY_KEY) || '';
    els.deviceCodeInput.value = urlDeviceCode.trim();
    els.apiBaseInput.value = CONFIG.API_BASE_URL;
    clearResult();
    bindEvents();
    if (urlDeviceCode.trim()) {
      connectDevice().catch((error) => showError(error));
    }
  }

  function bindEvents() {
    els.connectForm.addEventListener('submit', (event) => {
      event.preventDefault();
      connectDevice().catch((error) => showError(error));
    });
    els.recordButton.addEventListener('click', () => {
      if (state.phase === 'recording') {
        stopRecording();
        return;
      }
      startRecording().catch((error) => showError(error));
    });
    els.retryButton.addEventListener('click', () => {
      if (state.lastAudioBlob) {
        uploadVoice(state.lastAudioBlob, state.lastAudioFormat).catch((error) => showError(error));
      }
    });
    els.clearButton.addEventListener('click', clearResult);
    els.resetButton.addEventListener('click', resetPageState);
    els.playButton.addEventListener('click', () => playAudio(true));
    els.answerAudio.addEventListener('error', () => {
      showNotice('语音加载失败，请检查 audioUrl 是否可访问。', 'warn');
    });
  }

  async function connectDevice() {
    const deviceCode = els.deviceCodeInput.value.trim();
    if (!deviceCode) {
      throw new Error('请输入设备码');
    }
    state.deviceCode = deviceCode;
    state.device = null;
    CONFIG.API_BASE_URL = normalizeApiBase(els.apiBaseInput.value);
    els.apiBaseInput.value = CONFIG.API_BASE_URL;

    setPhase('connecting');
    showNotice('正在上报设备并检查授权...', 'warn');
    const activationPayload = await apiRequest(CONFIG.ACTIVATE_PATH, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [CONFIG.DEVICE_CODE_HEADER]: deviceCode,
      },
      body: JSON.stringify(buildActivationPayload(deviceCode)),
    });
    const activationSession = normalizeSessionPayload(activationPayload, deviceCode);
    state.device = activationSession;
    renderDevice(activationSession);

    if (activationSession.bindingStatus !== 'bound') {
      setPhase('pending');
      showNotice('设备已上报，待超级管理员在设备请求中绑定公司和应用。', 'warn');
      logDiagnostic('device.pending', {
        deviceCode,
        bindingStatus: activationSession.bindingStatus,
      });
      return;
    }

    showNotice('设备已授权，正在拉取运行配置...', 'warn');
    const configPayload = await apiRequest(buildSessionPath(deviceCode), {
      method: 'GET',
      headers: {
        [CONFIG.DEVICE_CODE_HEADER]: deviceCode,
      },
    });
    const session = normalizeSessionPayload(configPayload, deviceCode);
    state.device = session;
    renderDevice(session);
    setPhase('ready');
    showNotice('设备连接成功', 'ok');
    logDiagnostic('device.connected', {
      deviceCode,
      tenantId: session.tenantId || '',
      applicationId: session.applicationId || '',
    });
  }

  function buildActivationPayload(deviceCode) {
    const userAgent = navigator.userAgent || '';
    return {
      deviceCode,
      softwareVersion: 'device-chat-html-demo',
      systemVersion: userAgent,
      mainboardInfo: 'browser',
      deviceInfo: {
        source: 'device-chat',
        userAgent,
        language: navigator.language || '',
        pageUrl: location.href,
        screen: window.screen ? `${window.screen.width}x${window.screen.height}` : '',
      },
    };
  }

  function buildSessionPath(deviceCode) {
    const url = new URL(CONFIG.SESSION_PATH, 'http://local');
    if (!url.searchParams.has('deviceCode')) {
      url.searchParams.set('deviceCode', deviceCode);
    }
    return `${url.pathname}${url.search}`;
  }

  function normalizeSessionPayload(payload, fallbackDeviceCode) {
    const data = unwrapApiPayload(payload);
    const device = data.device || data;
    const application = data.application || {};
    return {
      deviceCode: data.deviceCode || device.deviceCode || device.code || fallbackDeviceCode,
      deviceName: data.deviceName || device.deviceName || device.name || fallbackDeviceCode,
      tenantId: data.tenantId || device.tenantId || device.tenant || '',
      status: data.status || device.status || (device.isEnabled === false ? 'disabled' : 'active'),
      asrEnabled: data.asrEnabled,
      ttsEnabled: data.ttsEnabled,
      llmEnabled: data.llmEnabled,
      applicationId: data.applicationId || application.id || '',
      applicationName: data.applicationName || application.name || '',
      bindingStatus: data.bindingStatus || device.bindingStatus || (data.application || device.applicationId ? 'bound' : 'pending'),
    };
  }

  async function startRecording() {
    if (!state.deviceCode) {
      await connectDevice();
    }
    ensureRecorderSupport();
    clearResult();

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      throw new Error(error && error.name === 'NotAllowedError'
        ? '无法访问麦克风，请在浏览器中允许麦克风权限后重试。'
        : '麦克风打开失败，请检查浏览器权限和输入设备。');
    }

    state.discardRecording = false;
    state.recordingStopPending = false;
    state.mediaStream = stream;
    state.pcmChunks = [];
    state.recordingStartedAt = Date.now();

    setPhase('recording');
    updateRealtimeQuestionText();
    showNotice('正在录音，请开始说话...', 'warn');
    startRealtimeAsr();
    setupPcmCapture(stream);
    startRecordingClock();
    state.maxRecordTimer = window.setTimeout(stopRecording, CONFIG.MAX_RECORD_SECONDS * 1000);
  }

  function stopRecording() {
    if (state.phase !== 'recording' || state.recordingStopPending) {
      return;
    }
    state.recordingStopPending = true;
    handleRecordingStopped().catch((error) => showError(error));
  }

  async function handleRecordingStopped() {
    stopRecordingClock();
    stopStream();
    state.recordingStopPending = false;
    if (state.discardRecording) {
      state.discardRecording = false;
      return;
    }
    const duration = Date.now() - state.recordingStartedAt;
    finishRealtimeAsr();
    if (duration < CONFIG.MIN_RECORD_MS) {
      closeRealtimeAsr();
      setPhase('ready');
      showError(new Error('录音时间太短，请重新说一遍'));
      return;
    }

    const format = 'pcm';
    const blob = new Blob(state.pcmChunks, { type: 'application/octet-stream' });
    if (!blob.size) {
      closeRealtimeAsr();
      setPhase('ready');
      showError(new Error('麦克风音频为空，请重新说一遍'));
      return;
    }

    state.lastAudioBlob = blob;
    state.lastAudioFormat = format;
    els.retryButton.disabled = false;
    try {
      await uploadVoice(blob, format);
    } catch (error) {
      showError(error);
    }
  }

  async function uploadVoice(audioBlob, format) {
    if (!state.deviceCode) {
      throw new Error('设备码为空，请先连接设备');
    }
    setPhase('processing');
    showNotice('正在识别语音并生成回答...', 'warn');
    const formData = new FormData();
    formData.append('audio', audioBlob, `voice-${Date.now()}.${format || 'webm'}`);
    formData.append('deviceCode', state.deviceCode);
    formData.append('format', format || 'webm');
    if (format === 'pcm') {
      formData.append('sampleRate', String(CONFIG.PCM_SAMPLE_RATE));
    }
    if (state.sessionId) {
      formData.append('sessionId', state.sessionId);
    }

    const startedAt = performance.now();
    const payload = await apiRequest(CONFIG.VOICE_CHAT_PATH, {
      method: 'POST',
      headers: {
        [CONFIG.DEVICE_CODE_HEADER]: state.deviceCode,
      },
      body: formData,
    });
    const data = unwrapApiPayload(payload);
    renderAnswer(data);
    setPhase('completed');
    const elapsed = Math.round(performance.now() - startedAt);
    logDiagnostic('voice.completed', {
      deviceCode: state.deviceCode,
      sessionId: state.sessionId,
      traceId: data.traceId || '',
      elapsed,
      status: 'ok',
    });
  }

  function startRealtimeAsr() {
    resetRealtimeTranscript();
    closeRealtimeAsr();

    if (!window.WebSocket) {
      handleRealtimeAsrError(new Error('当前浏览器不支持实时识别连接'));
      return;
    }

    let socket;
    try {
      socket = new WebSocket(buildAsrRealtimeWebSocketUrl(state.deviceCode));
    } catch (error) {
      handleRealtimeAsrError(error);
      return;
    }

    socket.binaryType = 'arraybuffer';
    state.asrSocket = socket;

    socket.onopen = () => {
      flushPendingRealtimeAudio(socket);
      logDiagnostic('asr.realtime.opened', { deviceCode: state.deviceCode });
    };
    socket.onmessage = handleRealtimeAsrMessage;
    socket.onerror = () => {
      handleRealtimeAsrError(new Error('实时 ASR 连接异常'));
    };
    socket.onclose = () => {
      if (state.asrSocket === socket) {
        state.asrSocket = null;
      }
      window.clearTimeout(state.asrFinishTimer);
      state.asrFinishTimer = 0;
    };
  }

  function handleRealtimeAsrMessage(event) {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }

    if (payload.type === 'asr.ready') {
      logDiagnostic('asr.realtime.ready', { deviceCode: state.deviceCode });
      return;
    }

    if (payload.type === 'asr.transcript' && payload.text) {
      appendRealtimeTranscript(String(payload.text), Boolean(payload.final));
      return;
    }

    if (payload.type === 'asr.done') {
      closeRealtimeAsr();
      return;
    }

    if (payload.type === 'asr.error') {
      handleRealtimeAsrError(new Error(payload.message || '实时 ASR 识别失败'));
    }
  }

  function appendRealtimeTranscript(text, isFinal) {
    const normalizedText = text.trim();
    if (!normalizedText) {
      return;
    }
    if (isFinal) {
      state.asrFinalText = state.asrFinalText
        ? `${state.asrFinalText}\n${normalizedText}`
        : normalizedText;
      state.asrLiveText = '';
    } else {
      state.asrLiveText = normalizedText;
    }
    updateRealtimeQuestionText();
  }

  function updateRealtimeQuestionText() {
    const text = getRealtimeTranscript();
    if (text) {
      setText(els.questionText, els.questionCount, text);
      return;
    }
    if (state.phase === 'recording') {
      setText(els.questionText, els.questionCount, '', '正在等待实时识别结果');
    }
  }

  function getRealtimeTranscript() {
    return [state.asrFinalText, state.asrLiveText].filter(Boolean).join('\n');
  }

  function resetRealtimeTranscript() {
    state.asrLiveText = '';
    state.asrFinalText = '';
    state.asrPendingBuffers = [];
  }

  function sendRealtimeAudio(buffer) {
    const socket = state.asrSocket;
    if (!socket) {
      return;
    }
    if (socket.readyState === WebSocket.CONNECTING) {
      state.asrPendingBuffers.push(buffer);
      if (state.asrPendingBuffers.length > CONFIG.ASR_PENDING_CHUNK_LIMIT) {
        state.asrPendingBuffers.shift();
      }
      return;
    }
    if (socket.readyState !== WebSocket.OPEN) {
      return;
    }
    socket.send(buffer);
  }

  function flushPendingRealtimeAudio(socket) {
    const pendingBuffers = state.asrPendingBuffers;
    state.asrPendingBuffers = [];
    if (socket.readyState !== WebSocket.OPEN) {
      return;
    }
    for (const buffer of pendingBuffers) {
      socket.send(buffer);
    }
  }

  function finishRealtimeAsr() {
    const socket = state.asrSocket;
    if (!socket) {
      return;
    }
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'asr.finish' }));
      window.clearTimeout(state.asrFinishTimer);
      state.asrFinishTimer = window.setTimeout(closeRealtimeAsr, CONFIG.ASR_FINISH_TIMEOUT);
      return;
    }
    if (socket.readyState === WebSocket.CONNECTING) {
      closeRealtimeAsr();
    }
  }

  function closeRealtimeAsr() {
    const socket = state.asrSocket;
    window.clearTimeout(state.asrFinishTimer);
    state.asrFinishTimer = 0;
    state.asrSocket = null;
    if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
      socket.close(1000, 'client_close');
    }
  }

  function handleRealtimeAsrError(error) {
    const message = error && error.message ? error.message : String(error);
    logDiagnostic('asr.realtime.error', {
      deviceCode: state.deviceCode,
      message,
    });
    if (state.phase === 'recording') {
      showNotice(`实时识别暂不可用，录音结束后仍会提交完整问答：${message}`, 'warn');
    }
  }

  async function apiRequest(path, options) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);
    const url = toApiUrl(path);
    try {
      const response = await fetch(url, {
        ...options,
        mode: 'cors',
        credentials: 'omit',
        signal: controller.signal,
      });
      const contentType = response.headers.get('content-type') || '';
      const rawText = await response.text();
      const payload = parseResponse(rawText, contentType);
      if (!response.ok) {
        throw new Error(extractMessage(payload) || `${response.status} ${response.statusText}`);
      }
      if (payload && typeof payload.code === 'number' && payload.code !== 0) {
        throw new Error(payload.message || mapErrorCode(payload.code));
      }
      return payload;
    } catch (error) {
      if (error && error.name === 'AbortError') {
        throw new Error('请求超时，请稍后重试');
      }
      if (error instanceof TypeError) {
        throw new Error('网络异常或跨域请求被拦截，请检查 API 地址与 CORS 配置');
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function renderDevice(session) {
    els.deviceNameText.textContent = session.deviceName || session.deviceCode || '-';
    els.deviceStateText.textContent = normalizeDeviceState(session);
    els.applicationText.textContent = session.applicationName || '-';
    els.sessionIdText.textContent = state.sessionId || '-';
  }

  function renderAnswer(data) {
    const question = data.questionText || data.question || data.asrText || '';
    const answer = data.answerText || data.answer || data.text || '';
    if (!question) {
      showNotice('ASR 没有识别出内容，请重新说一遍。', 'warn');
    }
    if (!answer) {
      throw new Error('回答生成失败，请稍后重试');
    }
    if (data.ttsError) {
      showNotice(`回答已生成，语音合成失败：${data.ttsError}`, 'warn');
    }

    state.sessionId = data.sessionId || state.sessionId;
    els.sessionIdText.textContent = state.sessionId || '-';
    setText(els.questionText, els.questionCount, question || '未识别到有效语音');
    setText(els.answerText, els.answerCount, answer);
    els.traceIdText.textContent = data.traceId ? `trace ${data.traceId}` : 'trace -';

    const audioSource = buildAudioSource(data);
    if (audioSource) {
      setAudioSource(audioSource);
      if (CONFIG.AUTO_PLAY_AUDIO) {
        playAudio(false);
      }
      showNotice('回答完成', 'ok');
    } else {
      els.playButton.disabled = true;
      showNotice('语音合成失败，但文本回答可查看。', 'warn');
    }
  }

  function buildAudioSource(data) {
    if (data.audioUrl) {
      return normalizeMediaUrl(data.audioUrl);
    }
    if (data.audioBase64) {
      const value = String(data.audioBase64);
      if (value.startsWith('data:')) {
        return value;
      }
      return `data:${data.audioContentType || 'audio/mpeg'};base64,${value}`;
    }
    return '';
  }

  function setAudioSource(src) {
    els.answerAudio.src = src;
    els.playButton.disabled = false;
  }

  function playAudio(fromUserGesture) {
    if (!els.answerAudio.src) {
      return;
    }
    els.answerAudio.play().then(() => {
      showNotice('正在播放语音回复', 'ok');
    }).catch(() => {
      if (!fromUserGesture) {
        showNotice('浏览器阻止自动播放，请点击播放语音。', 'warn');
      } else {
        showNotice('语音播放失败，请检查音频地址。', 'warn');
      }
    });
  }

  function clearResult() {
    resetRealtimeTranscript();
    setText(els.questionText, els.questionCount, '', '等待语音识别结果');
    setText(els.answerText, els.answerCount, '', '等待系统回答');
    els.traceIdText.textContent = 'trace -';
    els.answerAudio.removeAttribute('src');
    els.answerAudio.load();
    els.playButton.disabled = true;
    hideNotice();
  }

  function resetPageState() {
    if (state.phase === 'recording') {
      state.discardRecording = true;
      stopRecording();
    }
    stopRecordingClock();
    stopStream();
    closeRealtimeAsr();
    clearResult();
    state.device = null;
    state.sessionId = '';
    state.deviceCode = '';
    state.lastAudioBlob = null;
    state.lastAudioFormat = '';
    els.retryButton.disabled = true;
    els.deviceCodeInput.value = '';
    els.deviceNameText.textContent = '-';
    els.deviceStateText.textContent = '未连接';
    els.applicationText.textContent = '-';
    els.sessionIdText.textContent = '-';
    setPhase('idle');
  }

  function setPhase(phase) {
    state.phase = phase;
    const labels = {
      idle: '未连接设备',
      connecting: '正在连接设备...',
      pending: '设备待授权',
      ready: '设备连接成功',
      recording: '正在录音，请开始说话...',
      processing: '正在识别语音并生成回答...',
      completed: '回答完成',
      error: '发生错误',
    };
    els.globalStatus.dataset.tone = phase;
    els.globalStatusText.textContent = labels[phase] || phase;
    const canRecord = phase === 'recording' || (Boolean(state.device) && ['ready', 'completed', 'error'].includes(phase));
    els.recordButton.disabled = !canRecord;
    els.connectButton.disabled = phase === 'connecting' || phase === 'recording' || phase === 'processing';
    els.recorderStage.dataset.active = phase === 'recording' ? 'true' : 'false';
    els.recordButtonText.textContent = phase === 'recording' ? '正在录音，点击结束' : '按下开始说话';
  }

  function showError(error) {
    const message = error && error.message ? error.message : String(error);
    setPhase(state.deviceCode ? 'error' : 'idle');
    showNotice(message, 'error');
    logDiagnostic('error', {
      deviceCode: state.deviceCode,
      sessionId: state.sessionId,
      message,
    });
  }

  function showNotice(message, tone) {
    els.noticeBox.hidden = false;
    els.noticeBox.dataset.tone = tone || 'error';
    els.noticeBox.textContent = message;
  }

  function hideNotice() {
    els.noticeBox.hidden = true;
    els.noticeBox.textContent = '';
    els.noticeBox.removeAttribute('data-tone');
  }

  function setText(node, countNode, value, placeholder) {
    const text = value || placeholder || '';
    node.textContent = text;
    node.classList.toggle('placeholder', !value);
    countNode.textContent = `${value ? value.length : 0} 字`;
  }

  function ensureRecorderSupport() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !AudioContextClass) {
      throw new Error('当前浏览器不支持录音功能，请更换 Chrome、Edge 或 Safari 浏览器。');
    }
  }

  function setupPcmCapture(stream) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioContextClass();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;

    processor.onaudioprocess = (event) => {
      if (state.phase !== 'recording' || state.recordingStopPending) {
        return;
      }
      const channelData = event.inputBuffer.getChannelData(0);
      const pcm = encodePCM16(downsampleBuffer(channelData, audioContext.sampleRate));
      const pcmBuffer = pcm.buffer.slice(0);
      state.pcmChunks.push(pcmBuffer);
      sendRealtimeAudio(pcmBuffer);
    };

    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(audioContext.destination);
    state.audioContext = audioContext;
    state.audioSource = source;
    state.audioProcessor = processor;
    state.audioGain = silentGain;
  }

  function downsampleBuffer(buffer, inputSampleRate) {
    if (inputSampleRate === CONFIG.PCM_SAMPLE_RATE) {
      return buffer;
    }
    const sampleRateRatio = inputSampleRate / CONFIG.PCM_SAMPLE_RATE;
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
      result[offsetResult] = count ? accum / count : 0;
      offsetResult += 1;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  function encodePCM16(samples) {
    const output = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, samples[i]));
      output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return output;
  }

  function startRecordingClock() {
    updateRecordingTime();
    state.recordingTimer = window.setInterval(updateRecordingTime, 250);
  }

  function stopRecordingClock() {
    window.clearInterval(state.recordingTimer);
    window.clearTimeout(state.maxRecordTimer);
    state.recordingTimer = 0;
    state.maxRecordTimer = 0;
    els.recordingTime.textContent = '00:00';
  }

  function updateRecordingTime() {
    const elapsedSeconds = Math.floor((Date.now() - state.recordingStartedAt) / 1000);
    const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
    const seconds = String(elapsedSeconds % 60).padStart(2, '0');
    els.recordingTime.textContent = `${minutes}:${seconds}`;
  }

  function stopStream() {
    if (state.audioProcessor) state.audioProcessor.disconnect();
    if (state.audioSource) state.audioSource.disconnect();
    if (state.audioGain) state.audioGain.disconnect();
    if (state.audioContext) state.audioContext.close().catch(() => {});
    state.audioContext = null;
    state.audioSource = null;
    state.audioProcessor = null;
    state.audioGain = null;
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
  }

  function toApiUrl(path) {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${normalizeApiBase(CONFIG.API_BASE_URL)}${normalizedPath}`;
  }

  function buildAsrRealtimeWebSocketUrl(deviceCode) {
    const path = String(CONFIG.ASR_REALTIME_PATH || '/ws/asr/test/').trim();
    const apiBase = new URL(normalizeApiBase(CONFIG.API_BASE_URL), location.href);
    const url = /^wss?:\/\//i.test(path) || /^https?:\/\//i.test(path)
      ? new URL(path)
      : new URL(path.startsWith('/') ? path : `/${path}`, apiBase.origin);

    if (url.protocol === 'https:') {
      url.protocol = 'wss:';
    } else if (url.protocol === 'http:') {
      url.protocol = 'ws:';
    }
    if (!url.searchParams.has('deviceCode')) {
      url.searchParams.set('deviceCode', deviceCode);
    }
    return url.toString();
  }

  function normalizeApiBase(value) {
    const rawValue = String(value || '').trim() || DEFAULT_CONFIG.API_BASE_URL;
    return rawValue.replace(/\/+$/, '');
  }

  function normalizeMediaUrl(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (raw.startsWith('/')) {
      const api = new URL(normalizeApiBase(CONFIG.API_BASE_URL));
      return `${api.origin}${raw}`;
    }
    try {
      const mediaUrl = new URL(raw);
      if (['backend', 'solin_backend'].includes(mediaUrl.hostname)) {
        const api = new URL(normalizeApiBase(CONFIG.API_BASE_URL));
        mediaUrl.protocol = api.protocol;
        mediaUrl.host = api.host;
      }
      return mediaUrl.toString();
    } catch {
      return raw;
    }
  }

  function parseResponse(rawText, contentType) {
    if (!rawText) return {};
    if (contentType.includes('application/json')) {
      return JSON.parse(rawText);
    }
    try {
      return JSON.parse(rawText);
    } catch {
      return { detail: rawText };
    }
  }

  function unwrapApiPayload(payload) {
    if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'data')) {
      return payload.data || {};
    }
    return payload || {};
  }

  function extractMessage(payload) {
    if (!payload || typeof payload !== 'object') return '';
    return payload.message || payload.detail || payload.error || '';
  }

  function normalizeDeviceState(session) {
    if (session.bindingStatus === 'pending') return '待授权';
    if (session.bindingStatus === 'ignored') return '已忽略';
    const value = String(session.status || '').toLowerCase();
    if (['active', 'online', 'enabled', 'success'].includes(value)) return '已连接';
    if (['disabled', 'inactive'].includes(value)) return '已禁用';
    return session.status || '已连接';
  }

  function mapErrorCode(code) {
    const messages = {
      4000: '参数错误',
      4001: '设备码无效或设备未授权',
      4002: '当前设备已被禁用，请联系管理员',
      4003: '设备未授权',
      4100: '麦克风音频为空',
      4101: '音频格式不支持',
      4102: '音频文件过大',
      5001: '语音识别失败，请重新说一遍',
      5002: '回答生成失败，请稍后重试',
      5003: '语音合成失败，但文本回答可查看',
      5004: '模型配置缺失',
      5005: '知识库查询失败',
      9000: '服务内部异常',
    };
    return messages[code] || '请求失败';
  }

  function logDiagnostic(event, data) {
    console.info('[device-chat]', event, data);
  }

  init();
})();
