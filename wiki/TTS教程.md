## 下面是阿里云TTS教程

### 需求
1. TTS这个能作为一个单独的接口，供前端调用。
2. 这个接口就叫做阿里云TTS，后续我可能会接入其他的TTS服务比如 edge-tts ，豆包等，音色都是不一样的，你需要自行设计好良好的架构。

### 注意点
1. 能通过变量传递的参数不能写死
2. `text_to_synthesize`这个列表里面就是需要被TTS的文本
3. `DASHSCOPE_API_KEY`这个需要配置到 `backend\.env`里面（如果已配置请忽略）
4. `qwen3-tts-flash-realtime`这个model也需要配置到`backend\.env`里面
5. url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime' 一样需要配置到`backend\.env`里面
6. voice = 'Cherry'，这个代表音色，暂时也配置到`backend\.env`里面



```python
import os
import base64
import threading
import time
import dashscope
from dashscope.audio.qwen_tts_realtime import *

qwen_tts_realtime: QwenTtsRealtime = None
text_to_synthesize = [
    '对吧~我就特别喜欢这种超市，',
    '尤其是过年的时候',
    '去逛超市',
    '就会觉得',
    '超级超级开心！',
    '想买好多好多的东西呢！'
]

DO_VIDEO_TEST = False

def init_dashscope_api_key():
    """
        Set your DashScope API-key. More information:
        https://github.com/aliyun/alibabacloud-bailian-speech-demo/blob/master/PREREQUISITES.md
    """

    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    if 'DASHSCOPE_API_KEY' in os.environ:
        dashscope.api_key = os.environ[
            'DASHSCOPE_API_KEY']  # load API-key from environment variable DASHSCOPE_API_KEY
    else:
        dashscope.api_key = 'your-dashscope-api-key'  # set API-key manually



class MyCallback(QwenTtsRealtimeCallback):
    def __init__(self):
        self.complete_event = threading.Event()
        self.file = open('result_24k.pcm', 'wb')

    def on_open(self) -> None:
        print('connection opened, init player')

    def on_close(self, close_status_code, close_msg) -> None:
        self.file.close()
        print('connection closed with code: {}, msg: {}, destroy player'.format(close_status_code, close_msg))

    def on_event(self, response: str) -> None:
        try:
            global qwen_tts_realtime
            type = response['type']
            if 'session.created' == type:
                print('start session: {}'.format(response['session']['id']))
            if 'response.audio.delta' == type:
                recv_audio_b64 = response['delta']
                self.file.write(base64.b64decode(recv_audio_b64))
            if 'response.done' == type:
                print(f'response {qwen_tts_realtime.get_last_response_id()} done')
            if 'session.finished' == type:
                print('session finished')
                self.complete_event.set()
        except Exception as e:
            print('[Error] {}'.format(e))
            return

    def wait_for_finished(self):
        self.complete_event.wait()


if __name__  == '__main__':
    init_dashscope_api_key()

    print('Initializing ...')

    callback = MyCallback()

    qwen_tts_realtime = QwenTtsRealtime(
        # 如需使用指令控制功能，请将model替换为qwen3-tts-instruct-flash-realtime
        model='qwen3-tts-flash-realtime',
        callback=callback, 
        # 以下为华北2（北京）地域的URL，各地域的URL不同。
        url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime'
        )

    qwen_tts_realtime.connect()
    qwen_tts_realtime.update_session(
        voice = 'Cherry',
        response_format = AudioFormat.PCM_24000HZ_MONO_16BIT,
        # 如需使用指令控制功能，请取消下方注释，并将model替换为qwen3-tts-instruct-flash-realtime
        # instructions='语速较快，带有明显的上扬语调，适合介绍时尚产品。',
        # optimize_instructions=True,
        mode = 'server_commit'        
    )
    for text_chunk in text_to_synthesize:
        print(f'send text: {text_chunk}')
        qwen_tts_realtime.append_text(text_chunk)
        time.sleep(0.1)
    qwen_tts_realtime.finish()
    callback.wait_for_finished()
    print('[Metric] session: {}, first audio delay: {}'.format(
                    qwen_tts_realtime.get_session_id(), 
                    qwen_tts_realtime.get_first_audio_delay(),
                    ))

```