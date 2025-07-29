# sub2.py  —— 最终完整修复版（仅改图标切换）
from PyQt5.QtWidgets import QWidget, QPushButton
from ui.kimi import Ui_Form2
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QRect
from PyQt5 import QtCore
import threading
import pyaudio
import wave
import os
import json
import time
import pygame  # 用于语音控制

# ---------------- 录音识别常量 ----------------
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
TEMP_WAV = "temp.wav"

# 全局变量，延迟初始化
pa = None
model = None

# ---------------- 异步初始化线程 ----------------
class InitializationThread(QThread):
    progress_update = pyqtSignal(str)  # 进度信号
    init_finished = pyqtSignal(object, object)  # 初始化完成信号 (pa, model)
    init_error = pyqtSignal(str)  # 初始化错误信号
    
    def run(self):
        try:
            global pa, model
            
            self.progress_update.emit("🚀 语音AI系统启动中...")
            time.sleep(0.1)
            
            self.progress_update.emit("📱 正在导入依赖库...")
            from use.web import KimiBot, speak
            
            self.progress_update.emit("🎤 正在初始化音频系统...")
            pa = pyaudio.PyAudio()
            
            self.progress_update.emit("🧠 正在加载语音识别模型...")
            self.progress_update.emit("📂 加载中: vosk-model-small-cn-0.22")
            from vosk import Model, KaldiRecognizer
            model = Model("driver/vosk-model-small-cn-0.22")
            
            self.progress_update.emit("✅ 语音识别模型加载完成")
            self.progress_update.emit("🌐 正在初始化Kimi AI接口...")
            
            # 创建KimiBot实例（不设置gui_callback，后面动态设置）
            bot = KimiBot()
            self.progress_update.emit("✅ Kimi AI接口初始化完成")
            
            self.progress_update.emit("🎉 系统初始化完成!")
            self.progress_update.emit("💡 现在可以使用语音交互功能")
            
            # 发送初始化完成信号
            self.init_finished.emit(bot, speak)
            
        except Exception as e:
            error_msg = f"系统初始化失败: {str(e)}"
            self.progress_update.emit(f"❌ {error_msg}")
            self.init_error.emit(error_msg)

# ---------------- 信号桥 ----------------
class _SignalBridge(QObject):
    text_signal = pyqtSignal(str)
    answer_signal = pyqtSignal(str)

# ---------------- 录音线程 ----------------
class RecordThread(QThread):
    def __init__(self, form_instance):
        super().__init__()
        self.form_instance = form_instance
        self.frames = []

    def run(self):
        global pa, model
        
        # 检查是否已初始化
        if pa is None or model is None:
            self.form_instance.bridge.text_signal.emit("系统尚未初始化完成")
            return
            
        # 导入必要的模块
        from vosk import KaldiRecognizer
        
        self.frames.clear()
        stream = pa.open(format=FORMAT,
                         channels=CHANNELS,
                         rate=RATE,
                         input=True,
                         frames_per_buffer=CHUNK)
        while getattr(self, "_running", False):
            self.frames.append(stream.read(CHUNK, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()

        # 保存 wav
        with wave.open(TEMP_WAV, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pa.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))

        # 识别
        rec = KaldiRecognizer(model, RATE)
        with wave.open(TEMP_WAV, 'rb') as wf:
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                rec.AcceptWaveform(data)
            result = json.loads(rec.FinalResult())
        text = result.get("text", "").strip()

        # 通过父窗口的信号桥回到主线程
        self.form_instance.bridge.text_signal.emit(text)
        if os.path.exists(TEMP_WAV):
            os.remove(TEMP_WAV)

# ---------------- 主窗口 ----------------
class Form2(QWidget, Ui_Form2):
    def __init__(self, title="语言人工智能交互平台"):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 立即显示窗口
        self.show()
        
        # 强制处理UI事件，确保界面立即显示
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        # 初始化状态
        self.bot = None
        self.speak_func = None
        self.system_ready = False
        self.is_speaking = False  # 语音输出状态
        self.current_ai_response = ""  # 当前AI回答的完整内容
        self.last_display_pos = 0  # 上次显示位置
        self.last_speech_pos = 0  # 上次语音播报位置
        self.is_processing = False  # 是否正在处理AI回答
        self.speech_queue = []  # 语音播报队列
        
        # 显示初始化信息
        self.answer.setPlainText("🚀 语音AI系统启动中...\n💡 页面已就绪，正在初始化...")
        self.question.setPlainText("系统初始化中，请稍候...")

        # 信号桥
        self.bridge = _SignalBridge()
        self.bridge.text_signal.connect(self.on_recognized)
        self.bridge.answer_signal.connect(self.on_streaming_answer)

        # 录音按钮
        self.record_btn = self.findChild(QPushButton, "record")
        self.record_btn.setCheckable(True)
        self.record_btn.toggled.connect(self.toggle_record)
        
        # 初始禁用按钮
        self.record_btn.setEnabled(False)
        self.send.setEnabled(False)

        # 发送按钮
        self.send.clicked.connect(self.on_send)
        
        # 关闭按钮（pushButton_2 即×键）
        self.pushButton_2.clicked.disconnect()  # 断开原有的close连接
        self.pushButton_2.clicked.connect(self.close_with_speech_stop)
        
        # 使用QTimer延迟启动初始化，确保UI先显示
        QTimer.singleShot(100, self.start_initialization)

        # 窗口边缘拖动参数
        self._resize_dir = None
        self._resize_flag = False
        self.EDGE_MARGIN = 8
        self.CURSOR_MAP = {
            'left':  Qt.SizeHorCursor,
            'right': Qt.SizeHorCursor,
            'top':   Qt.SizeVerCursor,
            'bottom':Qt.SizeVerCursor,
            'lt':    Qt.SizeFDiagCursor,
            'rt':    Qt.SizeBDiagCursor,
            'lb':    Qt.SizeBDiagCursor,
            'rb':    Qt.SizeFDiagCursor,
        }

    # ---------- 录音控制 ----------
    def toggle_record(self, checked):
        if not self.system_ready:
            self.update_initialization_progress("⚠️ 系统尚未初始化完成，请稍候...")
            self.record_btn.setChecked(False)
            return
            
        # 如果正在处理AI回答或语音输出，先中断所有进程
        if self.is_processing or self.is_speaking:
            self.interrupt_all_processes()
            
        if checked:          # 开始录音
            self.answer.setPlainText("🎤 录音中...\n请说话，再次点击结束录音")
            self.record_btn.setIcon(QtGui.QIcon("images/录音按钮.png"))
            self.rec_thread = RecordThread(self)
            self.rec_thread._running = True
            self.rec_thread.start()
        else:                # 结束录音
            if hasattr(self, 'rec_thread'):
                self.rec_thread._running = False
                self.rec_thread.quit()
                self.rec_thread.wait()
            self.record_btn.setIcon(QtGui.QIcon("images/录音结束 (1).png"))   # ← 恢复默认图标
            self.answer.setPlainText("🔄 正在识别语音...\n请稍候...")

    def on_recognized(self, text):
        if text and text != "系统尚未初始化完成":
            self.question.setPlainText(text)
            self.answer.setPlainText(f"✅ 识别结果: {text}\n💡 点击发送按钮获取AI回答")
        elif text == "系统尚未初始化完成":
            self.answer.setPlainText("⚠️ 系统尚未初始化完成，请稍候...")
        else:
            self.question.setPlainText("未检测到语音")
            self.answer.setPlainText("❌ 未检测到有效语音\n💡 请重新尝试录音")

    # ---------- 发送 ----------
    def on_send(self):
        q = self.question.toPlainText().strip()
        if not q or q in ["请输入您的问题...", "系统初始化中，请稍候...", "初始化失败，仅支持文本输入"]:
            self.answer.setPlainText("⚠️ 请先输入有效问题")
            return
            
        # 如果正在处理AI回答或语音输出，先中断所有进程
        if self.is_processing or self.is_speaking:
            self.interrupt_all_processes()
            
        if not self.system_ready:
            self.answer.setPlainText("⚠️ 系统尚未完全初始化，正在尝试基础回答...")
            
        self.answer.setPlainText(f"🤔 正在思考您的问题...\n问题: {q}\n")
        self.reset_states()  # 重置状态
        threading.Thread(target=self._ask, args=(q,), daemon=True).start()

    def _ask(self, q):
        try:
            self.is_processing = True
            self.bridge.answer_signal.emit("🤖 AI正在回答:\n\n")
            
            # 复用现有的bot实例，不要重新创建
            if self.bot is None:
                from use.web import KimiBot
                self.bot = KimiBot(gui_callback=self._on_streaming_content)
            else:
                # 更新现有bot的回调函数
                self.bot.gui_callback = self._on_streaming_content
                
            answer = self.bot.send_message(q)
            
            # 处理完成后的清理
            self.is_processing = False
                
        except Exception as e:
            error_msg = f"❌ 获取回答时出错: {str(e)}"
            self.bridge.answer_signal.emit(error_msg)
            self.is_processing = False

    def _on_streaming_content(self, content):
        """处理流式输出内容"""
        if not self.is_processing:  # 如果已被中断，直接返回
            return
            
        if content.strip():
            # 累积完整内容
            self.current_ai_response = content
            # 更新显示
            self.bridge.answer_signal.emit(f"🤖 AI回答:\n\n{content}")
            
            # 实现同步的语音播报
            if self.speak_func is not None:
                self._process_speech_sync(content)

    def _process_speech_sync(self, content):
        """同步处理语音播报"""
        # 获取新增内容
        new_content = content[self.last_speech_pos:]
        
        if len(new_content) > 10:  # 积累一定字符后开始处理
            # 寻找句子边界
            sentence_markers = ['。', '！', '？', '.', '!', '?', '，', ',', '；', ';']
            best_end = -1
            
            # 从后往前寻找最佳断句点
            for i in range(len(new_content) - 1, max(0, len(new_content) - 50), -1):
                if new_content[i] in sentence_markers:
                    best_end = i
                    break
            
            if best_end > 5:  # 找到合适的断句点
                speech_text = new_content[:best_end + 1].strip()
                if speech_text and not self.is_speaking:
                    self.last_speech_pos += best_end + 1
                    # 立即开始语音播报，实现同步
                    threading.Thread(target=self._speak_immediately, args=(speech_text,), daemon=True).start()

    def _speak_immediately(self, text):
        """立即语音播报"""
        if not self.is_processing:  # 检查是否已被中断
            return
            
        try:
            self.is_speaking = True
            self.speak_func(text)
        except Exception as e:
            print(f"语音播报错误: {e}")
        finally:
            self.is_speaking = False

    def on_streaming_answer(self, text):
        """处理流式输出的回答"""
        self.answer.setPlainText(text)
        
        # 自动滚动到底部
        cursor = self.answer.textCursor()
        cursor.movePosition(cursor.End)
        self.answer.setTextCursor(cursor)

    def stop_speech(self):
        """停止当前语音输出"""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            self.is_speaking = False
        except Exception as e:
            print(f"停止语音出错: {e}")

    def stop_speech_and_reset(self):
        """停止语音并重置状态"""
        self.interrupt_all_processes()
        self.reset_states()
        print("语音输出已中断并重置状态")

    def close_with_speech_stop(self):
        """关闭窗口前先停止所有进程"""
        self.interrupt_all_processes()
        self.close()

    # ---------- 边缘拖动 ----------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self.isMaximized():
            self.m_flag = True
            self.m_Position = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QtGui.QCursor(QtCore.Qt.OpenHandCursor))
        if event.button() == QtCore.Qt.LeftButton and self._resize_dir:
            self._resize_flag = True
            self._resize_start = event.globalPos()
            self._start_geo = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if QtCore.Qt.LeftButton and getattr(self, 'm_flag', False):
            self.move(event.globalPos() - self.m_Position)
            event.accept()
            return
        if getattr(self, '_resize_flag', False) and self._resize_dir:
            delta = event.globalPos() - self._resize_start
            g = self._start_geo
            new_geo = QRect(g)
            if 'left'  in self._resize_dir: new_geo.setLeft  (g.left()   + delta.x())
            if 'right' in self._resize_dir: new_geo.setRight (g.right()  + delta.x())
            if 'top'   in self._resize_dir: new_geo.setTop   (g.top()    + delta.y())
            if 'bottom'in self._resize_dir: new_geo.setBottom(g.bottom() + delta.y())
            self.setGeometry(new_geo)
            event.accept()
        else:
            self._update_cursor_shape(event.pos())

    def mouseReleaseEvent(self, event):
        if getattr(self, 'm_flag', False):
            self.m_flag = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        if getattr(self, '_resize_flag', False):
            self._resize_flag = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

    def _update_cursor_shape(self, pos):
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        margin = self.EDGE_MARGIN
        left, right = x < margin, x > w - margin
        top, bottom = y < margin, y > h - margin
        if top and left:      self._resize_dir = 'lt'
        elif top and right:   self._resize_dir = 'rt'
        elif bottom and left: self._resize_dir = 'lb'
        elif bottom and right:self._resize_dir = 'rb'
        elif left:            self._resize_dir = 'left'
        elif right:           self._resize_dir = 'right'
        elif top:             self._resize_dir = 'top'
        elif bottom:          self._resize_dir = 'bottom'
        else:
            self._resize_dir = None
            self.setCursor(Qt.ArrowCursor)
            return
        self.setCursor(QtGui.QCursor(self.CURSOR_MAP[self._resize_dir]))

    # ---------- 异步初始化 ----------
    def start_initialization(self):
        """启动异步初始化"""
        self.init_thread = InitializationThread()
        self.init_thread.progress_update.connect(self.update_initialization_progress)
        self.init_thread.init_finished.connect(self.on_initialization_finished)
        self.init_thread.init_error.connect(self.on_initialization_error)
        self.init_thread.start()
        
    def update_initialization_progress(self, message):
        """更新初始化进度"""
        current_text = self.answer.toPlainText()
        # 保持最近8行信息
        lines = current_text.split('\n')
        if len(lines) > 8:
            lines = lines[-7:]  # 保留最近7行，加上新的一行
        
        lines.append(message)
        self.answer.setPlainText('\n'.join(lines))
        
        # 自动滚动到底部
        cursor = self.answer.textCursor()
        cursor.movePosition(cursor.End)
        self.answer.setTextCursor(cursor)
        
    def on_initialization_finished(self, bot, speak_func):
        """初始化完成"""
        self.bot = bot
        self.speak_func = speak_func
        self.system_ready = True
        
        # 初始化pygame mixer用于语音控制
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as e:
            print(f"pygame初始化失败: {e}")
        
        # 启用按钮
        self.record_btn.setEnabled(True)
        self.send.setEnabled(True)
        
        # 更新UI提示
        self.update_initialization_progress("=" * 40)
        self.update_initialization_progress("🎉 系统就绪，可以开始使用!")
        self.update_initialization_progress("💬 您可以:")
        self.update_initialization_progress("  • 在文本框输入问题")
        self.update_initialization_progress("  • 点击录音按钮进行语音输入")
        
        # 重置问题框
        self.question.setPlainText("请输入您的问题...")
        
    def on_initialization_error(self, error_message):
        """初始化错误"""
        self.update_initialization_progress("=" * 40)
        self.update_initialization_progress("❌ 系统初始化失败!")
        self.update_initialization_progress(f"错误信息: {error_message}")
        self.update_initialization_progress("请检查依赖环境和模型文件")
        
        # 只启用文本输入（假设KimiBot可能还能工作）
        self.send.setEnabled(True)
        self.question.setPlainText("初始化失败，仅支持文本输入")

    # ---------- 资源清理 ----------
    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        # 中断所有进程
        self.interrupt_all_processes()
        
        # 关闭浏览器实例
        if self.bot is not None:
            try:
                self.bot.quit_browser()
            except Exception as e:
                print(f"关闭浏览器出错: {e}")
        
        # 停止初始化线程
        if hasattr(self, 'init_thread') and self.init_thread.isRunning():
            self.init_thread.quit()
            self.init_thread.wait()
            
        # 清理临时文件
        if os.path.exists(TEMP_WAV):
            try:
                os.remove(TEMP_WAV)
            except:
                pass
                
        super().closeEvent(event)

    def reset_states(self):
        """重置所有相关状态"""
        self.current_ai_response = ""
        self.last_display_pos = 0
        self.last_speech_pos = 0
        self.is_processing = False
        self.speech_queue.clear()

    def interrupt_all_processes(self):
        """中断所有正在进行的进程"""
        # 停止处理标志
        self.is_processing = False
        
        # 停止语音输出
        self.stop_speech()
        
        # 如果有录音线程在运行，停止它
        if hasattr(self, 'rec_thread') and self.rec_thread.isRunning():
            self.rec_thread._running = False
            self.rec_thread.quit()
            self.rec_thread.wait()
        
        # 重置录音按钮状态
        self.record_btn.setChecked(False)
        self.record_btn.setIcon(QtGui.QIcon("images/录音结束 (1).png"))
        
        print("所有进程已中断")