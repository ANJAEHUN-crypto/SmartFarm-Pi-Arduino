# 스마트팜 웹 서비스

요구사항에 따른 웹 제어 + 스케줄 + 캠 촬영 구성입니다.

## 구성 요약

- **라즈베리파이**: 웹 서버(Flask), 시리얼 제어, 스케줄 실행, (선택) 캠 촬영
- **아두이노 우노 R4 Wi-Fi**: USB 시리얼로 4ch 릴레이 제어
- **릴레이**: 1ch(LED1), 2ch(PUMP1), 3ch(LED2), 4ch(PUMP2) — NO 접점

## 디렉터리 구조

```
├── README.md
├── requirements.txt
├── config.example.json   → 복사하여 config.json 생성
├── data/
│   ├── schedules.json    (스케줄 저장, 자동 생성)
│   └── photos/           (캠 촬영 저장)
├── arduino/
│   └── smart_farm_relay/
│       └── smart_farm_relay.ino
└── pi/
    ├── app.py              # Flask 웹 서버
    ├── serial_relay.py      # 아두이노 시리얼 제어
    ├── schedule_store.py   # 스케줄 저장/로드 (채널당 10개, 시각 순 정렬)
    ├── scheduler_service.py # 1분마다 스케줄 실행
    ├── camera_capture.py    # 일정 시간 촬영 (별도 실행 또는 cron)
    ├── static/
    │   ├── style.css
    │   └── app.js
    └── templates/
        └── index.html
```

## 사용 방법

### 1. 아두이노

1. `arduino/smart_farm_relay/smart_farm_relay.ino` 를 Arduino IDE로 열기
2. 릴레이 연결: 1ch→D2, 2ch→D3, 3ch→D4, 4ch→D5 (필요 시 `RELAY_PINS[]` 수정)
3. 보드/포트 선택 후 업로드
4. USB로 라즈베리파이에 연결

### 2. 라즈베리파이 (Pi)

```bash
cd pi
pip install -r ../requirements.txt
```

- 시리얼 포트: Linux에서는 보통 `/dev/ttyACM0`. 설정은 `config.json` 에서.
- 설정 파일 생성:
  ```bash
  cp ../config.example.json ../config.json
  # config.json 에서 "serial.port" 를 실제 포트로 수정 (예: /dev/ttyACM0)
  ```
- 웹 서버 실행:
  ```bash
  python app.py
  ```
- 브라우저: `http://라즈베리파이IP:5000`
- 페이지에서 "연결" 버튼으로 시리얼 연결 후 릴레이 ON/OFF, 스케줄 추가/삭제

### 3. 스케줄

- 채널당 최대 10개. ON 시각 / OFF 시각 / 요일(daily 또는 0,1,2,…) 설정
- 저장 시 ON 시각 기준으로 정렬되어 표시·실행됨
- 서버가 1분마다 현재 시각과 비교해 해당 시각에 ON/OFF 전송

### 4. 캠 (일정 시간 촬영)

- `config.json` 의 `camera.save_dir` 에 저장 (기본: `data/photos`)
- 1장만 촬영:
  ```bash
  cd pi && python camera_capture.py once
  ```
- 일정 간격으로 촬영하려면 cron 예시:
  ```bash
  # 매시 0분에 1장
  0 * * * * cd /home/pi/smart_farm/pi && python camera_capture.py once
  ```
- Pi 공식 카메라: `picamera2` 설치 후 사용. USB 캠: `opencv-python-headless` 로 `camera_capture.py` 내 USB 캠 경로 사용 가능.

## MQTT 사용 시 (선택)

- 웹만으로도 원격 ON/OFF·스케줄·촬영 가능.
- MQTT를 쓰려면 Pi에서 브로커(Mosquitto 등) 실행 후, Flask 앱에 MQTT 클라이언트를 붙여 토픽으로 ON/OFF/상태를 주고받게 하면 됩니다. 필요 시 별도 스크립트 `mqtt_bridge.py` 로 웹 API ↔ MQTT 연동 가능.

## 포트

- 웹: `5000`
- 시리얼: `config.json` 의 `serial.port` (예: `/dev/ttyACM0`)
