import datetime
from PySide6.QtWidgets import *

class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("실시간 시스템 로그")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("background-color: #1e1e1e; color: #4af626; font-family: Consolas; font-size: 12px;")
        layout.addWidget(self.text_edit)

    def append_log(self, text):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{now}] {text}")
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())