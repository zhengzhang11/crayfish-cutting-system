# Form4.py
import sys, cv2
import numpy as np
from PyQt5.QtWidgets import QWidget, QApplication, QTextEdit, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QRect, QSize
from PyQt5.QtGui import (QImage, QPixmap, QPainter, QPainterPath, QFont,
                         QRegion, QCursor, QResizeEvent)
from PyQt5 import QtCore, QtGui
from ui.seg import Ui_Form4          # ← 你的 ui 文件
from testseg import YOLOv11Seg       # ← 你的检测类


# ---------- 工具：生成带圆角的 QPixmap ----------
def rounded_pixmap(src: QPixmap, size: QSize, radius: int) -> QPixmap:
    """把 src 画到 size 大小的圆角 QPixmap 并返回"""
    dst = QPixmap(size)
    dst.fill(Qt.transparent)
    p = QPainter(dst)
    p.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    p.setClipPath(path)
    if not src.isNull():
        scaled = src.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        p.drawPixmap(0, 0, scaled)
    p.end()
    return dst


# ---------- 推理线程 ----------
class InferThread(QThread):
    infer_done = pyqtSignal(QPixmap, str, str)

    def __init__(self, detector, frame):
        super().__init__()
        self.detector = detector
        self.frame = frame

    def run(self):
        img, info_f, info_a = self.detector.detect(self.frame)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        qimg = QImage(rgb_img.data, w, h, ch * w, QImage.Format_RGB888)
        self.infer_done.emit(QPixmap.fromImage(qimg), info_f, info_a)


# ---------- 主窗口 ----------
class Form4(QWidget, Ui_Form4):
    def __init__(self, title="实例分割检测系统"):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ---------- 检测器 ----------
        self.detector = YOLOv11Seg(
            model_path="driver/bestseg.pt",
            label_path="driver/names2.txt",
            confThreshold=0.45,
            nmsThreshold=0.5,
            device='cpu'
        )

        # ---------- 摄像头 ----------
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.show_video)
        self.timer.start(30)

        # ---------- 按钮 ----------
        self.start.mousePressEvent = self.start_infer
        self.stop.mousePressEvent = self.stop_infer

        # ---------- 文本框样式 ----------
        mono = QFont("Consolas", 8)
        if not mono.exactMatch():
            mono = QFont("Courier New", 8)

        for te in (self.axis, self.feature):
            te.setFont(mono)
            te.setReadOnly(True)
            te.setFrameShape(QTextEdit.NoFrame)
            te.setStyleSheet("""
                QTextEdit{
                    border-radius:10px;
                    background:#fff;
                    padding:5px;
                    color:#000;
                }
            """)
        self.axis.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.feature.setWordWrapMode(QtGui.QTextOption.WordWrap)

        # ---------- 占位图 ----------
        self._placeholder = QPixmap(640, 480)
        self._placeholder.fill(Qt.transparent)

        # ---------- 缓存 ----------
        self._last_video_pix = QPixmap()
        self._last_image_pix = QPixmap()

        # ---------- 圆角半径 ----------
        self._radius = 10

        # ---------- 初始化 ----------
        self._update_masks()
        self._set_placeholder()

    # ---------- 圆角蒙版 ----------
    def _update_masks(self):
        for lbl in (self.video, self.image):
            if not lbl:
                continue
            rect = QtCore.QRectF(lbl.rect())
            path = QPainterPath()
            path.addRoundedRect(rect, self._radius, self._radius)
            reg = QRegion(path.toFillPolygon().toPolygon())
            lbl.setMask(reg)

    # ---------- 占位图 ----------
    def _set_placeholder(self):
        p = rounded_pixmap(self._placeholder, self.video.size(), self._radius)
        self.video.setPixmap(p)
        self.image.setPixmap(p)

    # ---------- 实时视频 ----------
    def show_video(self):
        ok, frame = self.cap.read()
        if ok:
            self._last_video_pix = self._mat_to_rounded_pixmap(frame, self.video.size())
            self.video.setPixmap(self._last_video_pix)

    # ---------- 推理 ----------
    def start_infer(self, ev):
        ok, frame = self.cap.read()
        if not ok:
            return
        self.axis.setPlainText("推理中...")
        self.feature.setPlainText("推理中...")
        self.image.clear()
        self.infer_thread = InferThread(self.detector, frame)
        self.infer_thread.infer_done.connect(self.show_result)
        self.infer_thread.start()

    def show_result(self, qpix, info_f, info_a):
        self._last_image_pix = rounded_pixmap(qpix, self.image.size(), self._radius)
        self.image.setPixmap(self._last_image_pix)
        self.feature.setPlainText(info_f)
        self.axis.setPlainText(info_a)

    def stop_infer(self, ev):
        if self.infer_thread and self.infer_thread.isRunning():
            self.infer_thread.quit()
            self.infer_thread.wait()
        self.image.clear()
        self.feature.clear()
        self.axis.clear()
        self._set_placeholder()

    # ---------- 通用：Mat -> 圆角 QPixmap ----------
    def _mat_to_rounded_pixmap(self, mat: np.ndarray, size: QSize) -> QPixmap:
        rgb = cv2.cvtColor(mat, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        return rounded_pixmap(QPixmap.fromImage(qimg), size, self._radius)

    # ---------- 窗口大小变化 ----------
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_masks()
        # 实时重绘当前帧/图，避免拉伸或黑边
        if not self._last_video_pix.isNull():
            self.video.setPixmap(rounded_pixmap(self._last_video_pix, self.video.size(), self._radius))
        if not self._last_image_pix.isNull():
            self.image.setPixmap(rounded_pixmap(self._last_image_pix, self.image.size(), self._radius))
        else:
            self._set_placeholder()

    # ---------- 优雅退出 ----------
    def closeEvent(self, e):
        self.stop_infer(None)
        self.cap.release()
        super().closeEvent(e)

    # ---------- 以下无边框窗口拖拽/缩放 ----------
    EDGE_MARGIN = 8
    CURSOR_MAP = {
        'left':  Qt.SizeHorCursor,
        'right': Qt.SizeHorCursor,
        'top':   Qt.SizeVerCursor,
        'bottom':Qt.SizeVerCursor,
        'lt':    Qt.SizeFDiagCursor,
        'rt':    Qt.SizeBDiagCursor,
        'lb':    Qt.SizeBDiagCursor,
        'rb':    Qt.SizeFDiagCursor,
    }

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            self.m_flag = True
            self.m_Position = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.OpenHandCursor))
        if event.button() == Qt.LeftButton and getattr(self, '_resize_dir', None):
            self._resize_flag = True
            self._resize_start = event.globalPos()
            self._start_geo = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if Qt.LeftButton and getattr(self, 'm_flag', False):
            self.move(event.globalPos() - self.m_Position)
            event.accept()
            return
        if getattr(self, '_resize_flag', False) and getattr(self, '_resize_dir', None):
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
            self.setCursor(QCursor(Qt.ArrowCursor))
        if getattr(self, '_resize_flag', False):
            self._resize_flag = False
            self.setCursor(QCursor(Qt.ArrowCursor))

    def _update_cursor_shape(self, pos):
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        margin = self.EDGE_MARGIN
        left, right = x < margin, x > w - margin
        top, bottom = y < margin, y > h - margin
        if top and left:        self._resize_dir = 'lt'
        elif top and right:     self._resize_dir = 'rt'
        elif bottom and left:   self._resize_dir = 'lb'
        elif bottom and right:  self._resize_dir = 'rb'
        elif left:              self._resize_dir = 'left'
        elif right:             self._resize_dir = 'right'
        elif top:               self._resize_dir = 'top'
        elif bottom:            self._resize_dir = 'bottom'
        else:
            self._resize_dir = None
            self.setCursor(QCursor(Qt.ArrowCursor))
            return
        self.setCursor(QCursor(self.CURSOR_MAP[self._resize_dir]))


# ---------- 入口 ----------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Form4()
    w.show()
    sys.exit(app.exec_())
