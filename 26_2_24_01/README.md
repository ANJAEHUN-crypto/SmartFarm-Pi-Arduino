# 스마트팜 웹 서비스

요구사항에 따른 웹 제어 + 스케줄 + 캠 촬영 구성입니다.

## 구성 요약

- **RS485** → **아두이노 R4 WiFi** (D6,D7,D8) → **라즈베리파이** (USB 시리얼) → **HiveMQ(MQTT)** → 웹 그래프
- **라즈베리파이**: 웹 서버(Flask), 시리얼 제어, 배지 수신·MQTT 퍼블리시, 스케줄 실행, (선택) 캠 촬영
- **아두이노 우노 R4 Wi-Fi**: USB 시리얼로 4ch 릴레이 제어 + RS485 배지 데이터 수신 후 Pi로 전달
- **릴레이**: 1ch(LED1), 2ch(PUMP1), 3ch(LED2), 4ch(PUMP2) — NO 접점

## 디렉터리 구조

```
├── README.md
├── requirements.txt
├── config.example.json   → 복사하여 config.json 생성
├── data/
│   ├── schedules.json     (스케줄 저장, 자동 생성)
│   ├── badge_history.json (배지 수신 기록, 그래프/API용)
│   └── photos/            (캠 촬영 저장)
├── arduino/
│   └── smart_farm_relay/
│       └── smart_farm_relay.ino
└── pi/
    ├── app.py              # Flask 웹 서버
    ├── serial_relay.py      # 아두이노 시리얼 제어
    ├── schedule_store.py   # 스케줄 저장/로드 (채널당 10개, 시각 순 정렬)
    ├── scheduler_service.py # 1분마다 스케줄 실행, 1초마다 배지 폴링
    ├── badge_mqtt.py       # 배지 수집 → HiveMQ 퍼블리시, data/badge_history.json
    ├── camera_capture.py    # 일정 시간 촬영 (별도 실행 또는 cron)
    ├── static/
    │   ├── style.css
    │   └── app.js
    └── templates/
        └── index.html
```

## 사용 방법

### 1. 아두이노 (우노 R4 WiFi)

**릴레이 결선 (기존)**

| 릴레이 채널 | 아두이노 핀 |
|------------|-------------|
| 1ch (LED1)  | D2 |
| 2ch (PUMP1) | D3 |
| 3ch (LED2)  | D4 |
| 4ch (PUMP2) | D5 |

**RS485 모듈(MAX485 등) 결선**

| RS485 모듈 단자 | 아두이노 핀 | 비고 |
|-----------------|-------------|------|
| RO (Receiver Out) | D6 | 수신 데이터 → 아두이노 |
| DI (Driver In)    | D7 | 아두이노 → 송신 데이터 |
| DE (Driver Enable) | D8 | HIGH=송신, LOW=수신 (RE와 함께 연결) |
| RE (Receiver Enable) | D8 | DE와 함께 D8 한 핀에 연결 |
| VCC | 5V | |
| GND | GND | |

- USB 시리얼(D0/D1)은 라즈베리파이와 통신용으로 사용하므로 RS485는 **D6(RX), D7(TX), D8(DE/RE)** 사용 권장.
- DE와 RE는 점퍼로 묶어서 D8 하나로 제어하면 됩니다.

1. `arduino/smart_farm_relay/smart_farm_relay.ino` 를 Arduino IDE로 열기
2. 위 결선대로 릴레이(2~5), RS485(6,7,8) 연결
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

## RS485 배지 + HiveMQ (MQTT)

- 아두이노가 RS485로 수신한 한 줄 데이터는 USB 시리얼로 `BADGE <내용>` 형태로 Pi에 전달됨.
- Pi는 1초마다 수신한 배지 줄을 `config.json` 의 `mqtt` 설정이 켜져 있으면 HiveMQ 토픽(`smartfarm/badge`)으로 퍼블리시함.
- **HiveMQ Cloud** 사용 시 포트 8883, TLS, username/password 필요. `config.json` 예시:
  ```json
  "mqtt": {
    "enabled": true,
    "broker": "YOUR_CLUSTER.s1.eu.hivemq.cloud",
    "port": 8883,
    "topic": "greenbean",
    "client_id": "smartfarm-pi",
    "username": "your_username",
    "password": "your_password",
    "tls": true
  }
  ```
- 센서에서 한 줄이 **JSON 문자열**이면(예: `{"sensor":"temp","value":25.5}`) 그대로 파싱해 `t`(타임스탬프)와 합친 하나의 JSON으로 토픽에 퍼블리시함.
- 배지 기록은 `data/badge_history.json` 에 저장되며, 웹의 **RS485 배지 데이터 (그래프)** 섹션과 `GET /api/badge/history?limit=100` API로 확인 가능.

## 연결 끊김 시 이메일 알림 (선택)

- `config.json` 의 `alert` 에서 `email_enabled: true` 로 두고 SMTP 정보·수신 주소(`to_email`)를 넣으면, 시리얼이 열려 있는데 `disconnect_seconds`(기본 300초) 동안 응답이 없을 때 한 번 이메일로 알림을 보냅니다. (재연결 후에는 다시 감지 가능.)

## 포트

- 웹: `5000`
- 시리얼: `config.json` 의 `serial.port` (예: `/dev/ttyACM0`)
