import cv2
import os
import traceback
from pyzbar.pyzbar import decode
from PySide6.QtCore import QThread, Signal

class CameraWorker(QThread):
    # 신호 정의 (UI 업데이트용)
    frame_signal = Signal(str, str, object)  # IP, MAC, 영상 프레임
    qr_signal = Signal(str, str, int)        # IP, MAC, 찾아낸 슬롯 번호
    log_signal = Signal(str)                 # 로그 메시지 전송용

    def __init__(self, ip, mac, use_gpu=True):
        super().__init__()
        self.ip = ip
        self.mac = mac
        self.use_gpu = use_gpu
        self.running = True
        self.check_qr = False
        self.found_slot = -1

    def run(self):
        self.log_signal.emit(f"[{self.ip}] 연결 시도 중...")

        # GPU 관련 옵션을 싹 빼고 안정성/속도 위주로만 세팅
        ffmpeg_opts = "rtsp_transport;tcp|analyzeduration;0|probesize;32|stimeout;10000000"
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = ffmpeg_opts
        rtsp_url = f"rtsp://admin:admin123!@{self.ip}/stream2"

        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                self.log_signal.emit(f"[{self.ip}] 에러: RTSP 스트림을 열 수 없습니다.")
                return

            self.log_signal.emit(f"[{self.ip}] 연결 성공. 영상 수신 시작.")

            frame_count = 0
            while self.running:
                try:
                    # [유지] CPU 부하를 1/10로 줄여주는 일등 공신 (수정 안 함!)
                    if not cap.grab():
                        self.msleep(50)
                        continue

                    frame_count += 1
                    if frame_count % 10 != 0: 
                        continue

                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue

                    # --- (이하 QR 스캔 및 리사이즈 로직은 기존과 완전 동일) ---
                    if self.check_qr:
                        try:
                            decoded = decode(frame)
                            for obj in decoded:
                                data = obj.data.decode('utf-8')
                                if data.startswith("SLOT_"):
                                    self.found_slot = int(data.split('_')[1])
                                    self.qr_signal.emit(self.ip, self.mac, self.found_slot)
                                    self.log_signal.emit(f"[{self.ip}] QR 인식 성공: 슬롯 {self.found_slot}번")
                                    self.check_qr = False
                                    break
                        except: pass

                    try:
                        small_frame = cv2.resize(frame, (200, 150))
                        self.frame_signal.emit(self.ip, self.mac, small_frame)
                    except: pass

                    self.msleep(10)

                except Exception as loop_err:
                    self.msleep(100)

        except Exception as e:
            self.log_signal.emit(f"[{self.ip}] 에러: {str(e)}")
        finally:
            if 'cap' in locals() and cap.isOpened():
                cap.release()
            self.log_signal.emit(f"[{self.ip}] 연결 종료.")

    def stop(self):
        self.running = False
        self.wait()