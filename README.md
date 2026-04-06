# 📷 QR IP Configurator

IP 카메라를 빠르게 세팅하기 위한 자동화 도구입니다. 
QR 코드를 스캔하여 물리적 위치(슬롯)를 자동으로 매핑하고, 다수의 카메라 IP를 충돌 없이 일괄 변경합니다.

## 🌟 핵심 기능
- **QR 기반 자동 매칭**: 카메라 화면에 QR 코드를 비추어 NVR 채널(슬롯) 번호와 1:1 자동 매핑.
- **스마트 IP 일괄 부여**: 
  - 슬롯 번호에 맞춘 절대값 IP 부여 
  - 순차적으로 나열된 슬롯 중간에 공백이 있어도 시작 IP부터 채우는 순차 부여 모드 지원
- **현장 최적화**: 
  - FFmpeg 옵션 튜닝(`analyzeduration=0`)으로 36대 동시 로딩 딜레이 최소화.
  - 멀티스레딩(Worker) 적용으로 대량 IP 변경 시 UI 멈춤 방지.
  - ARP 강제 바인딩으로 초기 세팅 시 발생하는 IP 충돌 원천 차단.

## 📂 프로젝트 구조
주요 로직과 UI가 분리되어 있습니다.

```text
📦 IP_SETTING_USING_QR
 ┣ 📂 ui/                  # 시각적 요소를 담당하는 GUI 폴더
 ┃ ┣ 📜 main_window.py     # 메인 레이아웃 및 전체 흐름 제어
 ┃ ┣ 📜 slot_widget.py     # 개별 카메라 화면(1칸) 위젯
 ┃ ┗ 📜 log_window.py      # 실시간 로그 팝업창
 ┣ 📂 utils/               # 독립적으로 실행 가능한 보조 도구
 ┃ ┗ 📜 generate_qr.py     # A4 인쇄용 36채널 QR코드 & PDF 자동 생성기. (이미 생성된 파일(qr_outputs)을 사용해도 정상작동 합니다.)
 ┣ 📜 api_handler.py       # 카메라 IP 변경용 HTTP 통신 (Digest Auth)
 ┣ 📜 camera_worker.py     # RTSP 영상 수신 및 QR 디코딩 (백그라운드 스레드)
 ┗ 📜 main.py              # 프로그램 실행 진입점 V
```

> **⚠️ 실행 시 주의사항**
> * 스캔 시 ARP 통신을 위해 반드시 **관리자 권한으로 cmd 실행 후** `main.py`를 실행해야 합니다!
> * QR 코드 PDF 출력이 필요한 경우 `python utils/generate_qr.py` 를 실행하세요.

## 🚀 필수 라이브러리 설치

```bash
pip install PySide6 opencv-python pyzbar scapy requests Pillow qrcode
```