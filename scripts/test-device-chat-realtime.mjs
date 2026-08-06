#!/usr/bin/env node

import { writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

const ROOT = resolve(import.meta.dirname, '..');
const LOG_PATH = resolve(ROOT, 'data.log');
const DEFAULT_DEVICE_CODE = 'apifox';
const DEFAULT_QUESTION = '你们公司有什么产品';
const DEFAULT_TIMEOUT_MS = 120_000;

function printHelp() {
  console.log(`用法：node scripts/test-device-chat-realtime.mjs [选项]

默认值：
  设备号：${DEFAULT_DEVICE_CODE}
  问题：  ${DEFAULT_QUESTION}
  地址：  ws://localhost:8880/ws/realtime/

选项：
  --device-code <设备号>  覆盖设备号
  --question <问题>      覆盖问题
  --ws-url <地址>        覆盖 WebSocket 地址
  --timeout <毫秒>       覆盖超时时间，默认 ${DEFAULT_TIMEOUT_MS}
  --help                 显示帮助

脚本使用文本模式的 agent.session.start，后端仍按三合一链路执行 LLM -> TTS，
并把完整请求、JSON 响应和 TTS 二进制响应（Base64）写入根目录 data.log。`);
}

function optionValue(args, name, fallback) {
  const index = args.indexOf(name);
  if (index === -1) return fallback;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) {
    throw new Error(`${name} 缺少参数值`);
  }
  return value;
}

function parseOptions() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    printHelp();
    process.exit(0);
  }

  const timeout = Number(optionValue(args, '--timeout', DEFAULT_TIMEOUT_MS));
  if (!Number.isFinite(timeout) || timeout <= 0) {
    throw new Error('--timeout 必须是大于 0 的毫秒数');
  }

  return {
    deviceCode: optionValue(args, '--device-code', DEFAULT_DEVICE_CODE).trim(),
    question: optionValue(args, '--question', DEFAULT_QUESTION).trim(),
    wsUrl: optionValue(
      args,
      '--ws-url',
      process.env.REALTIME_WS_URL || 'ws://localhost:8880/ws/realtime/',
    ),
    timeout,
  };
}

function now() {
  return new Date().toISOString();
}

function createLogWriter(options) {
  const records = [
    {
      type: 'test.started',
      at: now(),
      request: {
        method: 'GET',
        url: options.wsUrl,
        protocol: 'WebSocket',
        headers: {},
      },
      deviceCode: options.deviceCode,
      question: options.question,
    },
  ];

  let writing = Promise.resolve();
  const flush = () => {
    writing = writing.then(() => writeFile(LOG_PATH, `${JSON.stringify(records, null, 2)}\n`, 'utf8'));
    return writing;
  };

  return {
    add(record) {
      records.push({ at: now(), ...record });
      return flush();
    },
    finish(record) {
      records.push({ at: now(), ...record });
      return flush();
    },
    ready: flush(),
  };
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function dataToBinary(data) {
  if (data instanceof ArrayBuffer) {
    return Buffer.from(data);
  }
  if (ArrayBuffer.isView(data)) {
    return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  }
  if (data instanceof Blob) {
    return Buffer.from(await data.arrayBuffer());
  }
  throw new TypeError(`无法识别的 WebSocket 二进制响应类型：${Object.prototype.toString.call(data)}`);
}

async function run(options) {
  const log = createLogWriter(options);
  const command = {
    type: 'agent.session.start',
    id: `agent-session-${Date.now()}-${randomUUID().slice(0, 8)}`,
    payload: {
      deviceCode: options.deviceCode,
      text: options.question,
      requestId: `req-${randomUUID()}`,
      traceId: `trace-${randomUUID()}`,
    },
  };

  await log.add({
    direction: 'request',
    transport: 'websocket',
    event: command,
    raw: JSON.stringify(command),
  });

  return new Promise((resolveRun, rejectRun) => {
    const socket = new WebSocket(options.wsUrl);
    let settled = false;
    let timer;

    const settle = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, error ? 'test_failed' : 'test_completed');
      }
      if (error) rejectRun(error);
      else resolveRun();
    };

    const fail = async (error) => {
      const message = error instanceof Error ? error.message : String(error);
      await log.finish({ type: 'test.failed', error: message });
      settle(error instanceof Error ? error : new Error(message));
    };

    timer = setTimeout(() => {
      void fail(new Error(`WebSocket ${options.timeout}ms 内未收到 agent.done`));
    }, options.timeout);

    socket.addEventListener('open', async () => {
      await log.add({
        direction: 'transport',
        transport: 'websocket',
        event: { type: 'socket.open' },
      });
      socket.send(JSON.stringify(command));
    });

    socket.addEventListener('message', async (message) => {
      try {
        if (typeof message.data === 'string') {
          const event = parseJson(message.data);
          await log.add({
            direction: 'response',
            transport: 'websocket',
            event,
            raw: message.data,
          });

          if (event?.type === 'agent.error' || event?.type === 'llm.error' || event?.type === 'error') {
            const errorMessage = event.error?.message || event.message || event.payload?.message || '实时三合一返回错误';
            await fail(new Error(errorMessage));
            return;
          }
          if (event?.type === 'agent.done') {
            await log.finish({ type: 'test.completed', result: 'agent.done received' });
            settle();
          }
          return;
        }

        const binary = await dataToBinary(message.data);
        await log.add({
          direction: 'response',
          transport: 'websocket',
          event: {
            type: 'binary',
            contentType: 'audio/pcm',
            byteLength: binary.byteLength,
            base64: binary.toString('base64'),
          },
        });
      } catch (error) {
        await fail(error);
      }
    });

    socket.addEventListener('error', async () => {
      await log.add({
        direction: 'transport',
        transport: 'websocket',
        event: { type: 'socket.error' },
      });
      await fail(new Error(`WebSocket 连接失败：${options.wsUrl}`));
    });

    socket.addEventListener('close', async (event) => {
      await log.add({
        direction: 'transport',
        transport: 'websocket',
        event: {
          type: 'socket.close',
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        },
      });
      if (!settled) {
        await fail(new Error(`WebSocket 提前关闭，code=${event.code} reason=${event.reason || '无'}`));
      }
    });
  });
}

try {
  const options = parseOptions();
  await run(options);
  console.log(`三合一测试完成：${options.question}`);
  console.log(`完整请求/响应已写入：${LOG_PATH}`);
} catch (error) {
  console.error(`三合一测试失败：${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
