# sub1.py  ——  跨平台 MP3/MP4 播放器，零外部依赖
import os
import sys
import tempfile
import pygame
import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QWidget, QFileDialog, QApplication
import time
from ui.mu import Ui_Form1   # 由 ui_mu.py 提供
# -------------------------------------------------
# 用 moviepy 读取音轨并返回 pygame Sound 对象
# -------------------------------------------------
def audio_from_video(video_path: str):
    """
    返回 (sound, fps) 供 pygame 播放
    """
    import moviepy.editor as mp
    clip = mp.VideoFileClip(video_path)
    # 导出为临时 wav（16bit PCM，pygame 可直接播放）
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
        tmp_wav = f.name
    # 使用更快的编码器和较低的比特率
    clip.audio.write_audiofile(tmp_wav,
                               codec='pcm_s16le',
                               bitrate='192k',
                               verbose=False,
                               logger=None)   # 关闭日志
    sound = pygame.mixer.Sound(tmp_wav)
    return sound, clip.fps, tmp_wav  # 返回 fps 用于视频帧同步

# -------------------------------------------------
# 全新的音频管理器 - 真实控制 pygame.mixer.music
# -------------------------------------------------


class AudioManager:
    def __init__(self):
        self.audio_file = None
        self.is_playing = False
        self.total_duration = 0
        self._offset_sec = 0.0  # 记录上一次 seek 的位置

    def load(self, file_path, duration):
        """加载音频文件"""
        try:
            pygame.mixer.music.load(file_path)
            self.audio_file = file_path
            self.total_duration = duration
            self._offset_sec = 0.0
            return True
        except Exception as e:
            print(f"音频加载失败: {e}")
            return False

    def play(self, start_pos=0):
        """从指定位置开始播放"""
        try:
            pygame.mixer.music.play(start=start_pos)
            self._offset_sec = start_pos
            self.is_playing = True
            return True
        except Exception as e:
            print(f"音频播放失败: {e}")
            return False

    def pause(self):
        """暂停"""
        pygame.mixer.music.pause()
        self.is_playing = False

    def resume(self):
        """恢复"""
        pygame.mixer.music.unpause()
        self.is_playing = True

    def stop(self):
        """停止"""
        pygame.mixer.music.stop()
        self.is_playing = False
        self._offset_sec = 0.0

    def seek(self, position):
        """跳转到指定位置（秒）"""
        pygame.mixer.music.play(start=position)
        self._offset_sec = position
        if not self.is_playing:
            pygame.mixer.music.pause()

    def get_pos(self):
        """当前真实播放位置（秒）"""
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return self._offset_sec
        return self._offset_sec + pos_ms / 1000.0

    def is_busy(self):
        """是否正在播放"""
        return pygame.mixer.music.get_busy()

# -------------------------------------------------
# 视频帧渲染线程
# -------------------------------------------------
class VideoThread(QThread):
    updateFrame = pyqtSignal(np.ndarray)

    def __init__(self, video_path: str, fps: float, parent=None):
        super().__init__(parent)
        self.cap = cv2.VideoCapture(video_path)
        self.fps = fps
        self.running = True
        self.paused = False
        self.seek_frame = -1
        self.current_frame = 0

    def run(self):
        while self.running and self.cap.isOpened():
            if self.seek_frame >= 0:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.seek_frame)
                self.current_frame = self.seek_frame
                self.seek_frame = -1

            if not self.paused:
                ret, frame = self.cap.read()
                if not ret:
                    break
                self.updateFrame.emit(frame)
                self.current_frame += 1

            time.sleep(1 / self.fps)
        self.cap.release()

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def seek_to_frame(self, frame_num):
        self.seek_frame = frame_num

    def stop(self):
        self.running = False
        self.wait()

# -------------------------------------------------
# 媒体加载线程
# -------------------------------------------------
class LoadMediaThread(QThread):
    mediaLoaded = pyqtSignal(dict)
    mediaLoadFailed = pyqtSignal(str)

    def __init__(self, media_path, parent=None):
        super().__init__(parent)
        self.media_path = media_path

    def run(self):
        try:
            path = self.media_path
            ext = os.path.splitext(path)[1].lower()
            is_video = (ext == '.mp4')
            total_seconds = 0

            if is_video:
                try:
                    import moviepy.editor as mp
                    clip = mp.VideoFileClip(path)
                    total_seconds = int(clip.duration)
                    fps = clip.fps
                    clip.close()
                except Exception as e:
                    self.mediaLoadFailed.emit(f"moviepy无法处理视频: {e}")
                    return
            else: # mp3
                from mutagen.mp3 import MP3
                audio = MP3(path)
                total_seconds = int(audio.info.length)
                fps = None

            tmp_wav = None
            if is_video:
                try:
                    # 提取音频
                    import moviepy.editor as mp
                    clip = mp.VideoFileClip(path)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                        tmp_wav = f.name
                    clip.audio.write_audiofile(tmp_wav, codec='pcm_s16le', bitrate='192k', verbose=False, logger=None)
                    clip.close()
                except Exception as e:
                    self.mediaLoadFailed.emit(f"从视频提取音频失败: {e}")
                    return

            result = {
                'path': path,
                'is_video': is_video,
                'total_seconds': total_seconds,
                'fps': fps,
                'tmp_wav': tmp_wav
            }
            self.mediaLoaded.emit(result)

        except Exception as e:
            self.mediaLoadFailed.emit(f"加载媒体失败: {e}")


# -------------------------------------------------
# 主窗口
# -------------------------------------------------
class Form1(QWidget, Ui_Form1):
    def __init__(self, title="音乐 / 视频播放器"):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 基本变量
        self.media_path = None
        self.total_seconds = 0
        self.is_paused = False
        self.is_seeking = False
        self.playback_start_offset = 0
        self.is_video = False
        self.video_thread = None
        self.load_thread = None
        self.audio_manager = AudioManager()
        self.tmp_wav = None
        self.play_start_time = 0

        # 初始化 pygame
        pygame.mixer.init()

        # 信号连接
        self.btn_browse.clicked.connect(self.browse_media)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.slider_progress.sliderPressed.connect(self.start_seeking)
        self.slider_progress.sliderReleased.connect(self.seek_position)
        self.btn_reset.clicked.connect(self.reset_progress)

        # 定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)

        self._resize_dir = None
        self._resize_flag = False

    # ---------------------------------------------------------------
    # 以下 UI 交互代码与之前相同，直接沿用
    # ---------------------------------------------------------------
    EDGE_MARGIN = 8
    CURSOR_MAP = {
        'left': Qt.SizeHorCursor, 'right': Qt.SizeHorCursor,
        'top': Qt.SizeVerCursor, 'bottom': Qt.SizeVerCursor,
        'lt': Qt.SizeFDiagCursor, 'rt': Qt.SizeBDiagCursor,
        'lb': Qt.SizeBDiagCursor, 'rb': Qt.SizeFDiagCursor,
    }

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            self.m_flag = True
            self.m_Position = event.globalPos() - self.pos()
            event.accept()
        if event.button() == Qt.LeftButton and self._resize_dir:
            self._resize_flag = True
            self._resize_start = event.globalPos()
            self._start_geo = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and getattr(self, 'm_flag', False):
            self.move(event.globalPos() - self.m_Position)
            return
        if getattr(self, '_resize_flag', False) and self._resize_dir:
            delta = event.globalPos() - self._resize_start
            g = self._start_geo
            new_geo = g
            if 'left' in self._resize_dir: new_geo.setLeft(g.left() + delta.x())
            if 'right' in self._resize_dir: new_geo.setRight(g.right() + delta.x())
            if 'top' in self._resize_dir: new_geo.setTop(g.top() + delta.y())
            if 'bottom' in self._resize_dir: new_geo.setBottom(g.bottom() + delta.y())
            self.setGeometry(new_geo)
            return
        self._update_cursor_shape(event.pos())

    def mouseReleaseEvent(self, event):
        if getattr(self, 'm_flag', False):
            self.m_flag = False
            self.setCursor(Qt.ArrowCursor)
        if getattr(self, '_resize_flag', False):
            self._resize_flag = False
            self.setCursor(Qt.ArrowCursor)

    def _update_cursor_shape(self, pos):
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        margin = self.EDGE_MARGIN
        left, right = x < margin, x > w - margin
        top, bottom = y < margin, y > h - margin
        if top and left: self._resize_dir = 'lt'
        elif top and right: self._resize_dir = 'rt'
        elif bottom and left: self._resize_dir = 'lb'
        elif bottom and right: self._resize_dir = 'rb'
        elif left: self._resize_dir = 'left'
        elif right: self._resize_dir = 'right'
        elif top: self._resize_dir = 'top'
        elif bottom: self._resize_dir = 'bottom'
        else:
            self._resize_dir = None
            self.setCursor(Qt.ArrowCursor)
            return
        self.setCursor(self.CURSOR_MAP[self._resize_dir])
    # ---------------------------------------------------------------

    # ---------- 文件浏览 ----------
    def browse_media(self):
        folder = os.path.join(os.path.dirname(__file__), "songs")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择媒体文件", folder,
            "音视频 (*.mp3 *.mp4)")
        if path:
            self.load_media(path)

    # ---------- 加载 ----------
    def load_media(self, path):
        # 清理旧资源
        self.reset_progress()
        self.stop_video_thread()
        self.audio_manager.stop()

        if self.tmp_wav and os.path.exists(self.tmp_wav):
            try:
                os.remove(self.tmp_wav)
            except:
                pass # 忽略可能的权限错误
            self.tmp_wav = None

        self.label_cover.setText("正在加载中...")
        self.label_cover.setAlignment(Qt.AlignCenter)
        self.slider_progress.setEnabled(False)
        self.btn_play_pause.setEnabled(False)

        # 使用线程加载媒体
        self.load_thread = LoadMediaThread(path)
        self.load_thread.mediaLoaded.connect(self.on_media_loaded)
        self.load_thread.mediaLoadFailed.connect(self.on_media_load_failed)
        self.load_thread.start()

    def on_media_load_failed(self, error_message):
        print(error_message)
        self.label_cover.setText("加载失败!")
        self.slider_progress.setEnabled(True)
        self.btn_play_pause.setEnabled(True)

    def on_media_loaded(self, result):
        self.media_path = result['path']
        self.is_video = result['is_video']
        self.total_seconds = result['total_seconds']
        self.video_fps = result['fps']
        self.tmp_wav = result['tmp_wav']

        self.label_cover.setText(os.path.basename(self.media_path))
        self.label_cover.setAlignment(Qt.AlignCenter)
        self.slider_progress.setEnabled(True)
        self.btn_play_pause.setEnabled(True)

        if not self.is_video:
            self.label_3.setPixmap(QPixmap("images/视频播放.png").scaled(
                self.label_3.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # 准备音频
        audio_path = self.tmp_wav if self.is_video else self.media_path
        if not self.audio_manager.load(audio_path, self.total_seconds):
            self.on_media_load_failed(f"Pygame无法加载音频: {audio_path}")
            return

        self.slider_progress.setMaximum(self.total_seconds)
        self.slider_progress.setValue(0)
        self.update_time_labels(0, self.total_seconds)
        self.is_paused = True
        self.is_seeking = False
        self.playback_start_offset = 0
        self.play_start_time = 0
        self.btn_play_pause.setText("▶ 播放")

        if self.is_video:
            self.start_video_thread()

    # ---------- 视频线程 ----------
    def start_video_thread(self):
        self.stop_video_thread()
        if self.is_video and self.video_fps:
            self.video_thread = VideoThread(self.media_path, self.video_fps)
            self.video_thread.updateFrame.connect(self.show_video_frame)
            self.video_thread.start()
            if self.is_paused:
                self.video_thread.pause()

    def stop_video_thread(self):
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread = None

    def show_video_frame(self, frame):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        self.label_3.setPixmap(QPixmap.fromImage(q_img).scaled(
            self.label_3.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---------- 其余逻辑 ----------
    def start_seeking(self):
        if not self.media_path:
            return
        self.is_seeking = True

    def update_progress(self):
        if not self.media_path or self.is_seeking:
            return

        pos_sec = self.audio_manager.get_pos()
        if pos_sec >= self.total_seconds:
            self.slider_progress.setValue(self.total_seconds)
            self.update_time_labels(self.total_seconds, self.total_seconds)
            self.btn_play_pause.setText("▶ 播放")
            self.is_paused = True
            self.playback_start_offset = self.total_seconds
            self.audio_manager.stop()
            if self.is_video:
                self.stop_video_thread()
            return

        pos_sec = max(0, min(int(pos_sec), self.total_seconds))
        self.slider_progress.setValue(pos_sec)
        self.update_time_labels(pos_sec, self.total_seconds)

    def update_time_labels(self, current, total):
        cm, cs = divmod(current, 60)
        tm, ts = divmod(total, 60)
        self.label_current.setText(f"{cm:02d}:{cs:02d}")
        self.label_total.setText(f"{tm:02d}:{ts:02d}")

    def seek_position(self):
        if not self.media_path:
            return
        
        target_pos = self.slider_progress.value()
        self.playback_start_offset = target_pos

        # 核心修正：seek之后，根据拖动前的状态决定是继续播放还是保持暂停
        if not self.is_paused:
            # 如果之前在播放，seek后直接继续播放
            self.audio_manager.play(start_pos=target_pos)
        else:
            # 如果之前是暂停，seek后需要保持暂停状态
            # AudioManager.seek 内部会调用 play + pause
            self.audio_manager.seek(target_pos)

        if self.is_video and self.video_thread and self.video_fps:
            target_frame = int(target_pos * self.video_fps)
            self.video_thread.seek_to_frame(target_frame)
            # 视频线程的状态与主状态 self.is_paused 保持一致
            if self.is_paused:
                self.video_thread.pause()
            else:
                self.video_thread.resume()

        self.update_time_labels(target_pos, self.total_seconds)
        self.is_seeking = False # 在所有操作完成后再释放seeking标志

    def toggle_play_pause(self):
        if not self.media_path:
            return

        try:
            if self.is_paused:
                if not self.audio_manager.is_busy():
                    self.audio_manager.play(self.playback_start_offset)
                else:
                    self.audio_manager.resume()

                if self.is_video:
                    if not self.video_thread or not self.video_thread.isRunning():
                        self.start_video_thread()
                        if self.video_fps and self.playback_start_offset > 0:
                            target_frame = int(self.playback_start_offset * self.video_fps)
                            self.video_thread.seek_to_frame(target_frame)
                    else:
                        self.video_thread.resume()

                self.is_paused = False
                self.btn_play_pause.setText("⏸ 暂停")
            else:
                self.audio_manager.pause()
                self.playback_start_offset = self.audio_manager.get_pos()
                if self.is_video and self.video_thread:
                    self.video_thread.pause()
                self.is_paused = True
                self.btn_play_pause.setText("▶ 播放")
        except Exception as e:
            print(f"播放/暂停出错: {e}")

    def reset_progress(self):
        if not self.media_path:
            return
        self.audio_manager.stop()
        if self.is_video:
            self.stop_video_thread()
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.quit()
            self.load_thread.wait()

        self.slider_progress.setValue(0)
        self.update_time_labels(0, self.total_seconds)
        self.playback_start_offset = 0
        self.play_start_time = 0
        self.btn_play_pause.setText("▶ 播放")
        self.is_paused = True
        if self.is_video:
            self.start_video_thread()

    # ---------- 退出 ----------
    def closeEvent(self, event):
        self.audio_manager.stop()
        self.stop_video_thread()
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.quit()
            self.load_thread.wait()
            
        if self.tmp_wav and os.path.exists(self.tmp_wav):
            try:
                os.remove(self.tmp_wav)
            except:
                import threading
                def force_delete():
                    time.sleep(0.5)
                    try:
                        if os.path.exists(self.tmp_wav):
                            os.remove(self.tmp_wav)
                    except:
                        pass
                threading.Thread(target=force_delete, daemon=True).start()
        event.accept()

# ------------------- 启动 -------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Form1()
    w.show()
    sys.exit(app.exec_())