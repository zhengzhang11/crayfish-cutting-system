import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QMessageBox, QLineEdit
from PyQt5 import QtCore
from ui.login import Ui_MainWindow
from sub import Form
from PyQt5 import QtGui
from PyQt5.QtCore import Qt , QRect   
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)  # Hide the window frame
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # Connect buttons to their functions
        self.ui.pushButton.clicked.connect(self.login)
        #self.ui.cancelButton.clicked.connect(self.close)
        self.ui.lineEdit_2.setEchoMode(QLineEdit.Password)  # Set password field to hide input
        self._resize_dir = None
        self._resize_flag = False
        # ---------- 2. 窗口拖动 ----------

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



    def login(self):
        username = self.ui.lineEdit.text()
        password = self.ui.lineEdit_2.text()
        if username == "zhangzheng" and password == "123456":
            self.win1 = Form()
            self.win1.show()
            self.win1.raise_()               # 保证置顶
            self.win1.activateWindow()
            QMessageBox.information(self, "Login Successful", "Welcome!")
            self.hide()  # Hide the login window after successful login
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid credentials.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    sys.exit(app.exec_())
    