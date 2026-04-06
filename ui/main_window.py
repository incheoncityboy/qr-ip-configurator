from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from scapy.all import ARP, Ether, srp

from ui.log_window import LogWindow
from ui.slot_widget import SlotWidget
from camera_worker import CameraWorker
from api_handler import CameraAPI

class IPAssignWorker(QThread):
    progress_sig = Signal(int, int, str)
    log_sig = Signal(str)
    slot_result_sig = Signal(int, bool)
    finished_sig = Signal()

    def __init__(self, mapping, mac_dict, config):
        super().__init__()
        self.mapping = mapping
        self.mac_dict = mac_dict
        self.config = config

    def run(self):
        total = len(self.mapping)
        sorted_mapping = sorted(self.mapping.items(), key=lambda item: item[1])

        for idx, (ip, slot_id) in enumerate(sorted_mapping):
            if self.config['is_sequential']:
                target_ip = f"{self.config['base']}.{self.config['start_num'] + idx}"
            else:
                target_ip = f"{self.config['base']}.{self.config['start_num'] + slot_id - 1}"

            mac = self.mac_dict.get(ip)
            if not mac: continue

            # 진행 상황을 메인 화면 팝업으로 전달
            msg = f"슬롯 {slot_id}번 ({ip} ➔ {target_ip}) 변경 중..."
            self.progress_sig.emit(idx, total, msg)

            # API 호출 (하나씩 순차적으로 실행됨)
            success, log_msg = CameraAPI.set_ip_secure(
                ip, mac, target_ip, 
                self.config['gateway'], self.config['netmask'], 
                self.config['user'], self.config['pw']
            )

            # 깔끔해진 한 줄짜리 로그 전달
            status_mark = "✅" if success else "❌"
            self.log_sig.emit(f" {status_mark} [슬롯 {slot_id:02d}] {target_ip} {log_msg}")
            self.slot_result_sig.emit(slot_id, success)

        self.progress_sig.emit(total, total, "모든 IP 변경 작업 완료!")
        self.finished_sig.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IP Camera Slot Auto-Config (Advanced)")
        self.resize(1600, 1000)
        
        self.workers = []
        self.current_mapping = {}
        self.qr_results = {}
        self.found_devices = []
        
        self.log_window = LogWindow(self)
        self.setup_ui()

    def log(self, text):
        print(text)
        self.log_window.append_log(text)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # -----------------------------------------------------
        # [수정된 부분 1] 프로그램 시작 시 로그 창을 미리 만들고 숨겨둡니다.
        # (기존에 쓰시던 LogWindow 클래스가 임포트되어 있어야 합니다)
        self.log_window = LogWindow() 
        self.log_window.hide()
        # -----------------------------------------------------

        side_panel = QVBoxLayout()
        
        self.btn_show_log = QPushButton("📜 실시간 로그 보기")
        self.btn_show_log.setFixedHeight(35)
        self.btn_show_log.setStyleSheet("background-color: #34495e; color: white; font-weight: bold;")


        # [수정된 부분 1-1] 클릭 시 force_show_log 대신 toggle_log_window 연결
        self.btn_show_log.clicked.connect(self.toggle_log_window)
        side_panel.addWidget(self.btn_show_log)
        side_panel.addSpacing(20)

        side_panel.addWidget(QLabel("1. 스캔 IP 범위:"))
        self.scan_range_input = QLineEdit("192.168.1.0/24")
        side_panel.addWidget(self.scan_range_input)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("2. 제조사 필터:"))
        self.radio_markin = QRadioButton("마크인 (98:BF:F4)")
        self.radio_ant = QRadioButton("ANT (40:04:0C)")
        self.radio_markin.setChecked(True)
        side_panel.addWidget(self.radio_markin)
        side_panel.addWidget(self.radio_ant)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("3. 변경 시작 IP:"))
        self.target_ip_input = QLineEdit("192.168.1.111")
        side_panel.addWidget(self.target_ip_input)
        side_panel.addSpacing(20)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("4. 서브넷 마스크:"))
        self.netmask_input = QLineEdit("255.255.255.0")
        side_panel.addWidget(self.netmask_input)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("5. 게이트웨이 IP:"))
        self.gateway_input = QLineEdit("192.168.1.1")
        side_panel.addWidget(self.gateway_input)

        side_panel.addSpacing(20)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("6. 카메라 접속 아이디:"))
        self.user_input = QLineEdit("admin")
        side_panel.addWidget(self.user_input)

        side_panel.addSpacing(10)
        side_panel.addWidget(QLabel("7. 카메라 접속 비밀번호:"))
        self.pw_input = QLineEdit("admin123!")
        side_panel.addWidget(self.pw_input)

        side_panel.addSpacing(20)
        
        self.btn_discovery = QPushButton("STEP 1: 장치 스캔 (기본 슬롯 부여)")
        self.btn_discovery.setFixedHeight(40)
        self.btn_discovery.clicked.connect(self.run_discovery)
        
        self.btn_start_qr = QPushButton("STEP 2: QR 스캔 모드 ON")
        self.btn_start_qr.setFixedHeight(40)
        self.btn_start_qr.setEnabled(False)
        self.btn_start_qr.clicked.connect(self.run_qr_scan)

        # [신규] 미인식 카메라 현황을 보여주는 라벨
        self.label_unscanned = QLabel("")
        self.label_unscanned.setStyleSheet("font-size: 13px; padding: 5px;")
        self.label_unscanned.setWordWrap(True) # 내용이 길어지면 자동 줄바꿈
        self.label_unscanned.hide() # 평소엔 숨겨둠

        self.btn_match_slots = QPushButton("STEP 3: 전체 슬롯 매칭 (확정)")
        self.btn_match_slots.setFixedHeight(40)
        self.btn_match_slots.setEnabled(False)
        self.btn_match_slots.setStyleSheet("font-weight: bold;")
        self.btn_match_slots.clicked.connect(self.run_match_slots)
        
        self.btn_apply = QPushButton("STEP 4: 아이피 변경하기")
        self.btn_apply.setFixedHeight(40)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self.run_final_assign)

        side_panel.addWidget(self.btn_discovery)
        side_panel.addWidget(self.btn_start_qr)
        side_panel.addWidget(self.label_unscanned) # STEP 2 버튼 바로 아래에 배치
        side_panel.addWidget(self.btn_match_slots)
        side_panel.addWidget(self.btn_apply)
        side_panel.addStretch()

        self.grid = QGridLayout()
        self.slots = {}
        for i in range(1, 37): 
            s = SlotWidget(i)
            s.sig_confirm.connect(self.on_slot_confirm)
            s.sig_rescan.connect(self.on_slot_rescan)
            self.grid.addWidget(s, (i-1)//6, (i-1)%6) 
            self.slots[i] = s

        main_layout.addLayout(side_panel, 1)
        main_layout.addLayout(self.grid, 4)

    # -----------------------------------------------------
    # [수정된 부분 2] 토글 함수와 백그라운드 로그 업데이트 함수
    
    def toggle_log_window(self):
        """버튼을 누를 때마다 로그 창이 꺼졌다 켜졌다 합니다."""
        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.log_window.show()
            self.log_window.raise_()         # 창을 맨 앞으로 가져옴
            self.log_window.activateWindow() # 창 활성화 (포커스)

    def log(self, text):
        """백그라운드에서 로그 데이터를 계속 쌓아줍니다."""
        from datetime import datetime
        now = datetime.now().strftime("[%H:%M:%S]")
        msg = f"{now} {text}"
        
        print(msg) # 파이썬 터미널 창에도 출력 (확인용)
        
        # 로그 창이 숨겨져 있더라도 데이터는 계속 위젯에 추가됩니다.
        if hasattr(self, 'log_window'):
            # 주의: LogWindow 클래스 안에 로그 텍스트를 추가하는 함수 이름에 맞춰주세요.
            # (예: append_log, add_text 등. 만약 QPlainTextEdit를 쓴다면 appendPlainText)
            self.log_window.append_log(msg) 
    # -----------------------------------------------------

    
    def update_unscanned_status(self):
        total_cameras = len(self.current_mapping)
        scanned_qrs = set(self.qr_results.values())
        missing_count = total_cameras - len(scanned_qrs)

        if missing_count > 0:
            if not scanned_qrs:
                # 아예 스캔된 게 없으면 1번부터 전체 대수까지
                expected_qrs = set(range(1, total_cameras + 1))
            else:
                # 스캔된 QR 중 가장 큰 번호가 전체 대수보다 작거나 같으면 무조건 1~N번 사용으로 간주
                if max(scanned_qrs) <= total_cameras:
                    expected_qrs = set(range(1, total_cameras + 1))
                else:
                    # [스마트 추론] 만약 20대인데 29번 QR이 읽혔다면? (오프셋 사용)
                    # 스캔된 QR 중 가장 작은 번호를 시작점으로 잡아서 빈 이빨을 찾아냄
                    start_qr = min(scanned_qrs)
                    expected_qrs = set(range(start_qr, start_qr + total_cameras))
            
            # 전체 예상 QR 번호에서 현재 인식된 QR 번호들을 빼버림 (차집합)
            missing_qrs = sorted(expected_qrs - scanned_qrs)
            
            # 텍스트가 너무 길어져서 UI가 깨지는 걸 막기 위해 12개까지만 표시
            if len(missing_qrs) > 12:
                missing_strs = ", ".join(map(str, missing_qrs[:12])) + " ..."
            else:
                missing_strs = ", ".join(map(str, missing_qrs))
            
            self.label_unscanned.setStyleSheet("color: #f39c12; font-weight: bold; background-color: #2c3e50; border-radius: 5px;")
            
            # [핵심] 이제 화면 번호가 아니라 '찾아야 할 QR 번호'를 띄워줍니다!
            self.label_unscanned.setText(f"⏳ 남은 카메라: {missing_count}대\n(찾아야 할 QR: {missing_strs}번)")
        else:
            self.label_unscanned.setStyleSheet("color: #2ecc71; font-weight: bold; background-color: #27ae60; color: white; border-radius: 5px;")
            self.label_unscanned.setText("✅ 모든 카메라 QR 인식 완료!")
            
    def run_discovery(self):
        # [추가] UI 멈춤을 방지하기 위한 QTimer 임포트
        from PySide6.QtCore import QTimer, QThread
        from PySide6.QtWidgets import QMessageBox

        self.log(f"\n====================================")
        self.log(f"[초기화] 이전 작업을 모두 지우고 제로 베이스에서 시작합니다.")

        # UI 버튼 잠금 (스캔 중 조작 방지)
        self.btn_start_qr.setEnabled(False)
        self.btn_match_slots.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.label_unscanned.hide() 
        
        # 이전 작업 워커(좀비 스레드) 완전 초기화
        if not hasattr(self, 'zombie_workers'):
            self.zombie_workers = []
            
        for w in self.workers:
            w.running = False  
            try:
                w.frame_signal.disconnect()
                w.qr_signal.disconnect()
                if hasattr(w, 'log_signal'): # 새롭게 추가된 로그 시그널 끊기
                    w.log_signal.disconnect()
            except:
                pass
            self.zombie_workers.append(w)
            
        self.workers.clear() 
        self.zombie_workers = [w for w in self.zombie_workers if w.isRunning()]

        self.current_mapping.clear()
        self.qr_results.clear()
        self.found_devices.clear()
        for i in range(1, 37): 
            self.slots[i].reset_ui()

        raw_range = self.scan_range_input.text().strip()
        if len(raw_range.split('.')) == 3:
            target_range = f"{raw_range}.0/24"
        else:
            target_range = raw_range
            
        prefix = "98:BF:F4" if self.radio_markin.isChecked() else "40:04:0C"
        limit = 36 

        self.log(f"[스캔 시작] 범위: {target_range} | 필터: {prefix}")

        try:
            # Scapy를 이용한 네트워크 스캔
            from scapy.all import conf, srp, Ether, ARP
            target_ip = target_range.split('/')[0] if '/' in target_range else target_range.split('-')[0]
            correct_iface = conf.route.route(target_ip)[0]
            self.log(f"[네트워크] 사용 인터페이스: {correct_iface.name if hasattr(correct_iface, 'name') else correct_iface}")

            ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target_range), iface=correct_iface, timeout=3, verbose=False)
            
            all_found = []
            for _, received in ans:
                mac = received.hwsrc.upper().replace('-', ':')
                ip = received.psrc
                if mac.startswith(prefix):
                    all_found.append({'ip': ip, 'mac': mac})
                    self.log(f" └ 발견: {ip} | {mac}")
            
            self.found_devices = all_found[:limit]

            # 스캔된 장비들을 UI 슬롯과 연결하고 영상 수신 워커 할당
            for idx, dev in enumerate(self.found_devices):
                temp_id = idx + 1 
                self.current_mapping[dev['ip']] = temp_id
                self.slots[temp_id].ip = dev['ip'] 
                
                # [핵심 1] 방금 업그레이드한 CameraWorker 호출 (RTX 5060 하드웨어 가속 켜기)
                worker = CameraWorker(dev['ip'], dev['mac'], use_gpu=True)
                
                # [핵심 2] 시그널 연결. 로그 시그널(log_signal)을 창의 로그 출력 함수(self.log)에 연결
                worker.frame_signal.connect(self.on_frame_received)
                worker.qr_signal.connect(self.on_qr_found)
                worker.log_signal.connect(self.log)
                
                self.workers.append(worker)
                
                # [핵심 3] QThread.msleep() 대신 QTimer.singleShot 사용
                # 메인 UI가 얼어붙는 현상 없이, 0.15초 간격으로 백그라운드에서 부드럽게 접속을 시작합니다.
                QTimer.singleShot(idx * 150, worker.start)

            # 영상 로딩이 백그라운드에서 예약되었으므로 스캔 완료 처리를 즉시 진행
            self.btn_start_qr.setEnabled(True)
            self.log(f"[스캔 완료] 총 {len(self.found_devices)}대 영상 로딩 예약 완료.")
            
        except Exception as e:
            self.log(f"[에러] {str(e)}")
            QMessageBox.critical(self, "스캔 에러", str(e))

    @Slot(str, str, object)
    def on_frame_received(self, ip, mac, frame):
        target_slot = self.current_mapping.get(ip)
        if target_slot and target_slot in self.slots:
            self.slots[target_slot].update_feed(frame, ip, mac)

    def run_qr_scan(self):
        self.log(f"\n[QR 스캔] 모든 카메라 무한 대기 모드 ON")
        self.qr_results.clear()
        self.btn_match_slots.setEnabled(False)
        
        # QR 스캔 모드 켜지면 상태창 노출 및 초기 계산
        self.label_unscanned.show()
        self.update_unscanned_status()

        for ip, ui_slot in self.current_mapping.items():
            self.slots[ui_slot].hide_buttons()
            self.slots[ui_slot].set_overlay("QR 렌즈에 대기중...", "#f39c12") 

        for w in self.workers:
            w.found_slot = -1
            w.check_qr = True

    @Slot(str, str, int)
    def on_qr_found(self, ip, mac, real_slot_id):
        if ip in self.qr_results: return 
        
        self.log(f" └ [QR 인식] {ip} -> 슬롯 {real_slot_id}번")
        self.qr_results[ip] = real_slot_id
        
        current_ui_slot = self.current_mapping.get(ip)
        if current_ui_slot:
            self.slots[current_ui_slot].set_overlay(f"슬롯 {real_slot_id}", "#2ecc71") 
            self.slots[current_ui_slot].show_buttons() 
        
        self.update_unscanned_status() # 인식될 때마다 실시간 업데이트
        self.check_all_confirmed()

    @Slot(str)
    def on_slot_confirm(self, ip):
        current_ui_slot = self.current_mapping.get(ip)
        if current_ui_slot:
            self.slots[current_ui_slot].hide_buttons()
            self.slots[current_ui_slot].set_overlay(f"슬롯 {self.qr_results[ip]}\n(확정)", "#27ae60")
            self.log(f" └ [수동 확정] {ip} 카메라 슬롯 확정.")

    @Slot(str)
    def on_slot_rescan(self, ip):
        current_ui_slot = self.current_mapping.get(ip)
        if current_ui_slot:
            self.slots[current_ui_slot].hide_buttons()
            self.slots[current_ui_slot].set_overlay("QR 렌즈에 대기중...", "#f39c12")
            self.log(f" └ [다시 스캔] {ip} 카메라 재탐색 시작.")

        if ip in self.qr_results: del self.qr_results[ip]
        self.btn_match_slots.setEnabled(False) 
        
        self.update_unscanned_status() # 재스캔 누르면 다시 미인식 카운트로 돌아감

        for w in self.workers:
            if w.ip == ip:
                w.found_slot = -1
                w.check_qr = True
                break

    def check_all_confirmed(self):
        if len(self.qr_results) == len(self.current_mapping) and len(self.current_mapping) > 0:
            self.btn_match_slots.setEnabled(True)
            self.btn_match_slots.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
            self.log("[완료] 모든 카메라의 QR 인식이 끝났습니다. '전체 슬롯 매칭'을 눌러주세요.")

    def run_match_slots(self):
        self.log(f"\n[슬롯 매칭] 라우팅 테이블 재설정 중...")
        detected_slots = list(self.qr_results.values())
        if len(detected_slots) != len(set(detected_slots)):
            self.log("[매칭 에러] 충돌! 중복된 번호가 있습니다.")
            QMessageBox.critical(self, "충돌 발생", "서로 다른 카메라가 같은 슬롯 번호를 인식했습니다. '다시 스캔'을 눌러 수정하세요.")
            return

        for i in range(1, 37): self.slots[i].reset_ui()
        self.current_mapping = self.qr_results.copy()

        for ip, slot_id in self.current_mapping.items():
            self.slots[slot_id].ip = ip 
            self.slots[slot_id].set_status("#f1c40f")
            self.log(f" └ 제자리 배정: 슬롯 {slot_id}번 -> {ip}")

        self.btn_apply.setEnabled(True)
        self.btn_match_slots.setStyleSheet("font-weight: bold;") 

    def run_final_assign(self):
        if not self.current_mapping: return

        start_ip = self.target_ip_input.text()
        base = ".".join(start_ip.split('.')[:-1])
        start_num = int(start_ip.split('.')[-1])
        
        target_netmask = self.netmask_input.text().strip()
        target_gateway = self.gateway_input.text().strip()
        target_user = self.user_input.text().strip()
        target_pw = self.pw_input.text().strip()

        active_slots = sorted(list(self.current_mapping.values()))
        has_gaps_or_offset = False
        if active_slots[0] != 1 or active_slots != list(range(active_slots[0], active_slots[-1] + 1)):
            has_gaps_or_offset = True

        is_sequential = False 
        if has_gaps_or_offset:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("IP 부여 방식 선택")
            msg_box.setText("인식된 슬롯이 1번부터 시작하지 않거나 중간에 빈 슬롯이 있습니다.\n어떤 방식으로 IP를 부여하시겠습니까?")
            btn_seq = msg_box.addButton("빈틈없이 순차 부여", QMessageBox.ActionRole)
            btn_abs = msg_box.addButton("슬롯 번호 기준 부여", QMessageBox.ActionRole)
            msg_box.addButton("취소", QMessageBox.RejectRole)
            msg_box.exec()
            
            clicked = msg_box.clickedButton()
            if clicked == btn_seq: is_sequential = True
            elif clicked == btn_abs: is_sequential = False
            else: return 
        else:
            reply = QMessageBox.question(self, '확인', f"{len(self.current_mapping)}대의 IP를 변경하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return

        self.log(f"\n====================================")
        self.log(f"🚀 [IP 일괄 변경 시작] 총 {len(self.current_mapping)}대")

        # 1. 워커에 넘겨줄 설정값과 MAC 주소 사전 만들기
        config = {
            'base': base, 'start_num': start_num, 'is_sequential': is_sequential,
            'gateway': target_gateway, 'netmask': target_netmask,
            'user': target_user, 'pw': target_pw
        }
        mac_dict = {dev['ip']: dev['mac'] for dev in self.found_devices}

        # 2. 진행 상태를 보여줄 팝업창(Progress Bar) 세팅
        # (None을 넣어서 작업 중간에 '취소' 버튼을 누르지 못하게 막습니다. 꼬임 방지)
        self.progress_dialog = QProgressDialog("작업을 준비 중입니다...", None, 0, len(self.current_mapping), self)
        self.progress_dialog.setWindowTitle("IP 변경 진행 중")
        self.progress_dialog.setWindowModality(Qt.WindowModal) # 창 밖을 클릭하지 못하게 잠금
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        # 3. 백그라운드 작업자(Thread) 생성 및 실행 (화면 굳음 방지)
        self.assign_worker = IPAssignWorker(self.current_mapping, mac_dict, config)
        self.assign_worker.progress_sig.connect(self.on_assign_progress)
        self.assign_worker.log_sig.connect(self.log)
        self.assign_worker.slot_result_sig.connect(self.on_assign_slot_result)
        self.assign_worker.finished_sig.connect(self.on_assign_finished)
        
        self.assign_worker.start()

    # --- 백그라운드 작업자가 보내는 신호를 받는 수신기 함수들 ---
    @Slot(int, int, str)
    def on_assign_progress(self, current, total, msg):
        self.progress_dialog.setValue(current)
        self.progress_dialog.setLabelText(msg)

    @Slot(int, bool)
    def on_assign_slot_result(self, slot_id, success):
        if success:
            self.slots[slot_id].set_status("#2ecc71")
        else:
            self.slots[slot_id].set_status("#e74c3c")

    @Slot()
    def on_assign_finished(self):
        self.progress_dialog.setValue(self.progress_dialog.maximum())
        QMessageBox.information(self, "작업 완료", "IP 일괄 변경 작업이 끝났습니다.\n로그를 확인해주세요.")