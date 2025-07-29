# -*- coding: utf-8 -*-
# sub.py  —— 追加实时时间/日期/星期显示，其余逻辑不动
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QMessageBox, QWidget
from PyQt5 import QtCore
from ui.app import Ui_Form
from sub1 import Form1
from sub2 import Form2
from sub3 import From3
from sub4 import Form4
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QRect, QTimer, QDateTime   # ← 新增 QTimer/QDateTime
 
class Form(QWidget, Ui_Form):
    def __init__(self, title="app界面"):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(title)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # ===== 以下 3 行是新增：实时时钟 =====
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_datetime)
        self.clock_timer.start(1000)        # 每秒刷新，严格按时钟节拍
        self.update_datetime()              # 立即显示一次

        # 原有信号连接保持不变
        self.pushButton.clicked.connect(self.musical)
        self.pushButton_4.clicked.connect(self.kimi)
        self.pushButton_5.clicked.connect(self.yolo)
        self.pushButton_6.clicked.connect(self.seg)        
        self._resize_dir = None
        self._resize_flag = False

    # ===== 新增槽：刷新时间/日期/星期 =====
    def update_datetime(self):
        now = QDateTime.currentDateTime()
        self.time.setText(now.toString("HH:mm"))          # 例 12:34
        self.riqi.setText(now.toString("M月d日"))          # 例 7月18日
        self.xinqi.setText(now.toString("dddd"))           # 例 星期五

    # ---------- 以下原有代码全部不动 ----------
    def musical(self):
        self.form1 = Form1()
        self.form1.show()
        self.form1.raise_()
        self.form1.activateWindow()

    def kimi(self):
        try:
            # 立即创建并显示页面（在Form2的__init__中已经调用了show()）
            self.form2 = Form2()
            self.form2.raise_()
            self.form2.activateWindow()
            print("✓ Kimi AI页面已显示，系统正在后台初始化...")
        except Exception as e:
            print(f"✗ 创建Kimi AI页面失败: {e}")
            # 可以显示错误对话框
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"无法启动Kimi AI系统:\n{e}")

    def yolo(self):
        try:
            # 立即创建并显示页面（在From3的__init__中已经调用了show()）
            self.form3 = From3()
            self.form3.raise_()
            self.form3.activateWindow()
            print("✓ YOLO页面已显示，模型正在后台加载...")
        except Exception as e:
            print(f"✗ 创建YOLO页面失败: {e}")
            # 可以显示错误对话框
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"无法启动YOLO检测系统:\n{e}")

    def seg(self):
        self.form1 = Form4()
        self.form1.show()
        self.form1.raise_()
        self.form1.activateWindow()
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
            if 'left'  in self._resize_dir: new_geo.setLeft(g.left()   + delta.x())
            if 'right' in self._resize_dir: new_geo.setRight(g.right() + delta.x())
            if 'top'   in self._resize_dir: new_geo.setTop(g.top()     + delta.y())
            if 'bottom'in self._resize_dir: new_geo.setBottom(g.bottom()+ delta.y())
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
#-------------------------------------------------------------------------------------------------------------------