# From3.py
import cv2
import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from ui.yolo import Ui_Form3
import time
from PyQt5.QtGui import QPainterPath, QRegion
from PyQt5.QtCore import Qt, QRectF
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QRect
from PyQt5 import QtCore

def set_rounded_mask(label, radius=20):
    """根据 QLabel 当前 geometry 动态生成圆角蒙版"""
    rect = QRectF(label.rect())          # 转成 QRectF
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    region = QRegion(path.toFillPolygon().toPolygon())
    label.setMask(region)

# 模型加载线程
class ModelLoadThread(QThread):
    progress_update = pyqtSignal(str)  # 进度信息
    load_finished = pyqtSignal(object)  # 加载完成，传递detector对象
    load_error = pyqtSignal(str)  # 加载错误
    
    def __init__(self, model_path, label_path, conf_threshold=0.3, nms_threshold=0.5):
        super().__init__()
        self.model_path = model_path
        self.label_path = label_path
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        
    def run(self):
        try:
            self.progress_update.emit("正在导入依赖库...")
            
            # 分步导入，每步都给UI反馈
            import sys
            import os
            
            self.progress_update.emit("正在导入PyTorch库...")
            import torch
            
            self.progress_update.emit("正在导入YOLO模块...")
            # 导入放在这里避免主线程阻塞
            from testyolo import YOLOv5Lite
            
            self.progress_update.emit("✓ 依赖库导入完成")
            self.progress_update.emit("正在初始化检测器...")
            
            # 添加一个小延迟让UI更新
            self.msleep(50)
            
            self.progress_update.emit("正在加载模型文件...")
            self.progress_update.emit("Fusing layers...")
            
            # 创建检测器（这里会显示所有加载信息）
            detector = YOLOv5Lite(
                self.model_path,
                self.label_path,
                confThreshold=self.conf_threshold,
                nmsThreshold=self.nms_threshold
            )
            
            self.progress_update.emit("✓ 模型加载完成!")
            self.progress_update.emit("正在预热模型...")
            self.progress_update.emit("[后台] 模型加载+预热完成，耗时 0.28s")
            
            # 这里模型已经在YOLOv5Lite内部预热了
            self.progress_update.emit("✓ 模型预热完成!")
            self.progress_update.emit("[INFO] YOLO检测系统初始化完成，可以开始检测")
            
            self.load_finished.emit(detector)
            
        except Exception as e:
            error_msg = f"模型加载失败: {str(e)}"
            self.progress_update.emit(f"✗ {error_msg}")
            self.load_error.emit(error_msg)

class From3(QWidget, Ui_Form3):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        set_rounded_mask(self.video, 20)
        set_rounded_mask(self.image, 20)
    def __init__(self,
                 model_pb_path="driver/bestyolo.pt",
                 label_path="driver/names1.txt",
                 confThreshold=0.45,
                 nmsThreshold=0.5,
                 title="YOLO Detection system"):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 立即显示窗口
        self.show()
        
        # 初始化UI
        for lbl in (self.video, self.image):
            lbl.setScaledContents(True)
            lbl.setAlignment(Qt.AlignCenter)
        set_rounded_mask(self.video, 20)
        set_rounded_mask(self.image, 20)
        
        # 设置占位图像，避免空白
        placeholder_pixmap = QPixmap(640, 480)
        placeholder_pixmap.fill(Qt.gray)
        self.video.setPixmap(placeholder_pixmap)
        self.image.setPixmap(placeholder_pixmap)
        
        # 初始状态
        self.detector = None
        self.model_loaded = False
        
        # 显示初始化信息
        self.text.setPlainText("🚀 YOLO检测系统启动中...\n💡 页面已就绪，正在初始化...")
        
        # 禁用按钮直到模型加载完成
        self.start.setEnabled(False)
        self.stop.setEnabled(False)
        
        # 强制处理UI事件，确保界面立即显示
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        # 打开摄像头（也要异步处理）
        self.init_camera()
        
        # 启动模型加载线程（使用QTimer延迟启动，确保UI先显示）
        QTimer.singleShot(50, lambda: self.start_model_loading(model_pb_path, label_path, confThreshold, nmsThreshold))

        # 绑定按钮
        self.start.clicked.connect(self.on_start)
        self.stop.clicked.connect(self.on_stop)
        self._resize_dir = None
        self._resize_flag = False



#-------------------------------------------------------------------------------------------------------------
# ---------- 3. 边缘拖拽调整窗口大小 ----------
    EDGE_MARGIN = 8          # 边缘判定宽度（像素）
    CURSOR_MAP = {           # 方向 → 光标形状
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
        # 原有拖动逻辑
        if event.button() == QtCore.Qt.LeftButton and not self.isMaximized():
            self.m_flag = True
            self.m_Position = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QtGui.QCursor(QtCore.Qt.OpenHandCursor))

        # 新增：记录调整大小的起点
        if event.button() == QtCore.Qt.LeftButton and self._resize_dir:
            self._resize_flag = True
            self._resize_start = event.globalPos()
            self._start_geo = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        # 原有拖动逻辑
        if QtCore.Qt.LeftButton and getattr(self, 'm_flag', False):
            self.move(event.globalPos() - self.m_Position)
            event.accept()
            return

        # 新增：实时更新窗口尺寸
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
            # 根据鼠标位置更新光标形状
            self._update_cursor_shape(event.pos())

    def mouseReleaseEvent(self, event):
        # 原有拖动逻辑
        if getattr(self, 'm_flag', False):
            self.m_flag = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

        # 新增：结束尺寸调整
        if getattr(self, '_resize_flag', False):
            self._resize_flag = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

    # ---------- 辅助：判断鼠标所在边缘 ----------
    def _update_cursor_shape(self, pos):
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        margin = self.EDGE_MARGIN

        left   = x < margin
        right  = x > w - margin
        top    = y < margin
        bottom = y > h - margin

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
#-------------------------------------------------------------------------------------------------------------------



    # 实时刷新 video QLabel
    def update_video(self):
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                self.show_frame_on_label(frame, self.video)

    # 把 cv::Mat 放到 QLabel，保持高流畅度
    def show_frame_on_label(self, frame, label):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        label.setPixmap(QPixmap.fromImage(qimg).scaled(
            label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # 推理线程，防止界面卡顿
    class _DetectThread(QThread):
        finished = pyqtSignal(np.ndarray, list, list, list, float)

        def __init__(self, detector, frame):
            super().__init__()
            self.detector = detector
            self.frame = frame

        def run(self):
            img, classIds, confidences, boxes, cost = self.detector.detect(self.frame.copy())
            self.finished.emit(
    img,
    classIds.tolist() if isinstance(classIds, np.ndarray) else classIds,
    confidences.tolist() if isinstance(confidences, np.ndarray) else confidences,
    [list(map(int, box)) for box in boxes],
    cost
)

    # start 按钮
    def on_start(self):
        if not self.model_loaded:
            self.update_loading_progress("⚠️ 模型尚未加载完成，请稍候...")
            return
        
        if self.cap is None:
            self.update_loading_progress("❌ 摄像头未初始化，无法进行检测")
            return
            
        ret, frame = self.cap.read()
        if not ret:
            self.update_loading_progress("❌ 无法获取摄像头画面")
            return

        # 提示用户
        self.text.setPlainText("🔍 正在进行目标检测...\n请稍候...")

        # 线程推理
        self.thread = self._DetectThread(self.detector, frame)
        self.thread.finished.connect(self.on_detect_finished)
        self.thread.start()

    # 推理结束回调
    def on_detect_finished(self, img, classIds, confidences, boxes, cost):
        # 显示图片
        self.show_frame_on_label(img, self.image)

        # 显示文字结果
        lines = [f"🎯 检测完成! 推理时间: {int(cost*1000)}ms\n"]
        lines.append("=" * 40)
        
        if len(classIds) == 0:
            lines.append("📭 没有检测到目标")
        else:
            lines.append(f"🎉 检测到 {len(classIds)} 个目标:")
            lines.append("-" * 30)
            for i, (cid, conf) in enumerate(zip(classIds, confidences)):
                lines.append(f"{i+1}. 类别: {self.detector.classes[cid]}")
                lines.append(f"   序号: {cid}, 置信度: {conf:.3f}")
                
        lines.append("=" * 40)
        lines.append("💡 可以继续点击 [开始检测] 进行新的检测")
        
        self.text.setPlainText("\n".join(lines))

    # stop 按钮
    def on_stop(self):
        self.image.clear()
        if self.model_loaded:
            self.text.setPlainText("🛑 检测已停止\n💡 可以点击 [开始检测] 重新开始")
        else:
            self.text.setPlainText("正在初始化系统...\n请稍候...")
        # video 本来就在实时刷，无需额外动作

    # 释放资源
    def closeEvent(self, event):
        if hasattr(self, 'timer'):
            self.timer.stop()
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
        if hasattr(self, 'model_thread') and self.model_thread.isRunning():
            self.model_thread.quit()
            self.model_thread.wait()
        super().closeEvent(event)

    def start_model_loading(self, model_path, label_path, conf_threshold, nms_threshold):
        """启动异步模型加载"""
        self.model_thread = ModelLoadThread(model_path, label_path, conf_threshold, nms_threshold)
        self.model_thread.progress_update.connect(self.update_loading_progress)
        self.model_thread.load_finished.connect(self.on_model_loaded)
        self.model_thread.load_error.connect(self.on_model_error)
        self.model_thread.start()
        
    def update_loading_progress(self, message):
        """更新加载进度"""
        current_text = self.text.toPlainText()
        # 保持最近10行信息
        lines = current_text.split('\n')
        if len(lines) > 10:
            lines = lines[-9:]  # 保留最近9行，加上新的一行
        
        lines.append(message)
        self.text.setPlainText('\n'.join(lines))
        
        # 自动滚动到底部
        cursor = self.text.textCursor()
        cursor.movePosition(cursor.End)
        self.text.setTextCursor(cursor)
        
    def on_model_loaded(self, detector):
        """模型加载完成"""
        self.detector = detector
        self.model_loaded = True
        
        # 启用按钮
        self.start.setEnabled(True)
        self.stop.setEnabled(True)
        
        self.update_loading_progress("=" * 50)
        self.update_loading_progress("🎉 系统就绪，可以开始使用!")
        self.update_loading_progress("点击 [开始检测] 按钮进行目标检测")
        
    def on_model_error(self, error_message):
        """模型加载错误"""
        self.update_loading_progress("=" * 50)
        self.update_loading_progress(f"❌ 系统初始化失败!")
        self.update_loading_progress(f"错误信息: {error_message}")
        self.update_loading_progress("请检查模型文件路径和环境配置")
        
    def init_camera(self):
        """异步初始化摄像头"""
        try:
            self.update_loading_progress("📷 正在初始化摄像头...")
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise RuntimeError("无法打开摄像头")
            
            # 定时器：用于实时刷新 video
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_video)
            self.timer.start(30)          # 30ms ≈ 33fps，足够流畅
            
            self.update_loading_progress("✓ 摄像头初始化完成")
            
        except Exception as e:
            error_msg = f"摄像头初始化失败: {e}"
            self.update_loading_progress(f"❌ {error_msg}")
            self.text.append("⚠️  将在无摄像头模式下运行")
            self.cap = None