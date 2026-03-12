# 패치/배포 이력

각 차수별로 적용된 변경 사항을 정리한 문서입니다.

---

## 1차 배포 (초기)

- **내용**: Git 저장소 최초 푸시, PC → GitHub 연동
- **대상**: 전체 프로젝트 (README, config, pi/, arduino/, data/ 등)
- **비고**: 라즈베리파이에서 `git clone` 으로 수신

---

## 2차 배포 (RS485 + HiveMQ + 배지·알림)

- **아두이노**
  - RS485 수신 추가 (D6 RX, D7 TX, D8 DE/RE)
  - 수신한 한 줄을 `BADGE ` 접두사로 USB 시리얼 전달
- **라즈베리파이**
  - `serial_relay.py`: 시리얼 리더 스레드, BADGE 줄 수집, `get_pending_badge_lines()`, `get_last_activity()`
  - `badge_mqtt.py`: 배지 데이터 → HiveMQ(MQTT) 퍼블리시, `data/badge_history.json` 저장
  - `alert_email.py`: 연결 끊김 감지 시 이메일 발송 (config.alert)
  - `config.json` / `config.example.json`: mqtt, alert 섹션 추가
- **웹**
  - `/api/badge/history` API 추가
  - RS485 배지 데이터(그래프) 섹션, Chart.js 단일 라인(건수)

---

## 3차 배포 (Modbus 토양센서 + JSON)

- **아두이노**
  - Modbus RTU 토양센서 연동 (온도·습도·EC·pH)
  - 3초마다 `BADGE {"status":"success","soil_temperature":...,"soil_humidity":...,"soil_EC":...,"soil_ph":...}` 전송
  - 릴레이 ON/OFF/STATE 프로토콜 유지
- **비고**: Pi 쪽은 기존 BADGE + JSON 파싱으로 그대로 수신·저장·MQTT 전송

---

## 4차 배포 (주간 표시 + 4값 추이 + 7일 삭제)

- **라즈베리파이**
  - `badge_mqtt.py`: 저장 시 7일 초과 데이터 삭제, `get_badge_history(limit=..., days=7)` 지원
  - `app.py`: `/api/badge/history` 기본 `days=7`, `limit=2000`
- **웹**
  - 그래프: 주간(7일) 데이터 요청, **온도·습도·EC·pH 4선** 한 차트에 표시
  - 섹션 제목: "토양 센서 주간 변화 추이 (온도·습도·EC·pH)"
  - 안내 문구: "최근 7일만 표시·저장, 7일 지난 데이터 자동 삭제"

---

## 5차 배포 (지표별 4개 그래프 + 축 고정)

- **웹**
  - **지표별 그래프 4개** 분리: 온도 / 습도 / EC / pH 각각 전용 차트 (2×2 그리드)
  - **Y축 고정**: 온도 0~50°C, 습도 0~100%, EC 0~2000 µS/cm, pH 0~14
  - **X축 고정**: 최근 400개 구간 고정, `animation: false` 로 갱신 시 가독성 유지
- **수정 파일**: `index.html`, `style.css`, `app.js`

---

## 참고

- 배포 후 Pi: `cd /home/pi/SmartFarm-Pi-Arduino && git pull origin main`  
- 앱 재시작: `cd 26_2_24_01 && source venv/bin/activate && python3 pi/app.py`  
- 웹 캐시 반영: 브라우저 **Ctrl+F5** (강력 새로고침)
