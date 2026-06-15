(function () {
  'use strict';

  const DEFAULT_CONFIG = {
    API_BASE_URL: location.protocol === 'file:' ? 'http://localhost:8880/api/v1' : `${location.origin}/api/v1`,
    DEVICE_CODE_QUERY_KEY: 'deviceCode',
    DEVICE_CODE_HEADER: 'X-Device-Code',
    ACTIVATE_PATH: '/device-auth/activate/',
    SESSION_PATH: '/device-runtime/config/',
    VOICE_CHAT_PATH: '/device/voice-chat',
    MAX_RECORD_SECONDS: 60,
    MIN_RECORD_MS: 700,
    REQUEST_TIMEOUT: 30000,
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
    mediaRecorder: null,
    mediaStream: null,
    chunks: [],
    recordingStartedAt: 0,
    recordingTimer: 0,
    maxRecordTimer: 0,
    lastAudioBlob: null,
    lastAudioFormat: '',
    phase: 'idle',
    discardRecording: false,
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

    const mimeType = selectMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    state.discardRecording = false;
    state.mediaStream = stream;
    state.mediaRecorder = recorder;
    state.chunks = [];
    state.recordingStartedAt = Date.now();

    recorder.addEventListener('dataavailable', (event) => {
      if (event.data && event.data.size > 0) {
        state.chunks.push(event.data);
      }
    });
    recorder.addEventListener('stop', () => handleRecordingStopped(mimeType));
    recorder.start(250);
    setPhase('recording');
    showNotice('正在录音，请开始说话...', 'warn');
    startRecordingClock();
    state.maxRecordTimer = window.setTimeout(stopRecording, CONFIG.MAX_RECORD_SECONDS * 1000);
  }

  function stopRecording() {
    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      state.mediaRecorder.stop();
    }
  }

  async function handleRecordingStopped(mimeType) {
    stopRecordingClock();
    stopStream();
    if (state.discardRecording) {
      state.discardRecording = false;
      return;
    }
    const duration = Date.now() - state.recordingStartedAt;
    if (duration < CONFIG.MIN_RECORD_MS) {
      setPhase('ready');
      showError(new Error('录音时间太短，请重新说一遍'));
      return;
    }

    const format = mimeToFormat(mimeType);
    const blob = new Blob(state.chunks, { type: mimeType || 'audio/webm' });
    if (!blob.size) {
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
      return `data:audio/mpeg;base64,${value}`;
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
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      throw new Error('当前浏览器不支持录音功能，请更换 Chrome、Edge 或 Safari 浏览器。');
    }
  }

  function selectMimeType() {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/wav',
    ];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || '';
  }

  function mimeToFormat(mimeType) {
    if (!mimeType) return 'webm';
    if (mimeType.includes('wav')) return 'wav';
    if (mimeType.includes('mp4')) return 'mp4';
    if (mimeType.includes('mpeg')) return 'mp3';
    return 'webm';
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
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach((track) => track.stop());
      state.mediaStream = null;
    }
    state.mediaRecorder = null;
  }

  function toApiUrl(path) {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${normalizeApiBase(CONFIG.API_BASE_URL)}${normalizedPath}`;
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
