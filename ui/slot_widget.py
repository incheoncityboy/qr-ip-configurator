from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class SlotWidget(QFrame):
    sig_confirm = Signal(str)
    sig_rescan = Signal(str)

    def __init__(self, slot_id):
        super().__init__()
        self.slot_id = slot_id
        self.ip = None 
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.label_title = QLabel(f"SLOT {self.slot_id}")
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.view = QLabel("Waiting...")
        self.view.setFixedSize(160, 120)
        self.view.setStyleSheet("background-color: #222; color: #555;")
        self.view.setAlignment(Qt.AlignCenter)
        
        self.overlay = QLabel(self.view)
        self.overlay.setGeometry(0, 0, 160, 120)
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.hide()
        
        self.info = QLabel("MAC: - \nIP: -")
        self.info.setAlignment(Qt.AlignCenter)
        
        self.btn_layout = QHBoxLayout()
        self.btn_confirm = QPushButton("✅ 확인")
        self.btn_rescan = QPushButton("🔄 다시 스캔")
        
        self.btn_confirm.clicked.connect(lambda: self.sig_confirm.emit(self.ip))
        self.btn_rescan.clicked.connect(lambda: self.sig_rescan.emit(self.ip))
        
        self.btn_layout.addWidget(self.btn_confirm)
        self.btn_layout.addWidget(self.btn_rescan)
        
        self.btn_confirm.hide()
        self.btn_rescan.hide()

        layout.addWidget(self.label_title)
        layout.addWidget(self.view)
        layout.addLayout(self.btn_layout)
        layout.addWidget(self.info)

    def show_buttons(self):
        self.btn_confirm.show()
        self.btn_rescan.show()

    def hide_buttons(self):
        self.btn_confirm.hide()
        self.btn_rescan.hide()

    def set_overlay(self, text, color):
        self.overlay.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold; background-color: rgba(0,0,0,160);")
        self.overlay.setText(text)
        self.overlay.show()

    def hide_overlay(self):
        self.overlay.hide()

    def set_status(self, color):
        if color == "none":
            self.setStyleSheet("SlotWidget { border: 2px solid #555; }")
        else:
            self.setStyleSheet(f"SlotWidget {{ border: 3px solid {color}; }}")

    def reset_ui(self):
        self.view.clear()
        self.view.setText("이동됨")
        self.info.setText("MAC: - \nIP: -")
        self.set_status("none")
        self.hide_overlay()
        self.hide_buttons()
        self.ip = None

    def update_feed(self, frame, ip, mac):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.view.setPixmap(QPixmap.fromImage(q_img).scaled(160, 120, Qt.KeepAspectRatio))
        self.info.setText(f"MAC: {mac}\nCurr IP: {ip}")