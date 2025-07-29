import pyaudio
import threading
import wave
import os
from pynput import keyboard
import speech_recognition as sr

# -------------------- 录音参数 --------------------
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
WAVE_OUTPUT = "temp.wav"

frames = []
recording = False
stream = None
pa = pyaudio.PyAudio()

# -------------------- 线程：录音 --------------------
def record_thread():
    global stream, frames
    frames.clear()
    stream = pa.open(format=FORMAT,
                     channels=CHANNELS,
                     rate=RATE,
                     input=True,
                     frames_per_buffer=CHUNK)
    while recording:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

# -------------------- 空格键回调 --------------------
import sys   # 新增

def on_press(key):
    global recording, stream

    if key == keyboard.Key.esc:            # <--- 新增：ESC 强制退出
        recording = False                  # 先让录音线程自己结束
        if stream and stream.is_active():
            stream.stop_stream()
            stream.close()
        pa.terminate()
        print("\n已退出")
        os._exit(0)                        # 立即终止整个进程

    elif key == keyboard.Key.space:
        if not recording:
            recording = True
            print("【开始录音】请说话...")
            threading.Thread(target=record_thread, daemon=True).start()
        else:
            recording = False
            print("【结束录音】正在识别...")
            save_and_recognize()
            print("按【空格】开始下一次录音；按【ESC】退出程序\n")

from vosk import Model, KaldiRecognizer
import json

model_path = "driver\\vosk-model-small-cn-0.22"  # 模型目录

import wave
import json
from vosk import Model, KaldiRecognizer

# -------------------- 全局变量 --------------------
model = Model("driver/vosk-model-small-cn-0.22")
rec   = KaldiRecognizer(model, 16000)

# --------------- 保存并识别（修改后） ---------------
def save_and_recognize():
    # 1. 写 wav
    with wave.open("temp.wav", 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))

    # 2. 识别
    rec.Reset()          # 清空上一次状态
    with wave.open("temp.wav", 'rb') as wf:
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)
        result = json.loads(rec.FinalResult())

    text = result.get("text", "").strip()
    if text:
        print("识别结果：", text)
    else:
        print("未检测到")

    # 3. 删除临时文件
    os.remove("temp.wav")

# -------------------- 主入口 --------------------
if __name__ == '__main__':
    print("按【空格】开始/结束录音；按【ESC】退出程序")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()