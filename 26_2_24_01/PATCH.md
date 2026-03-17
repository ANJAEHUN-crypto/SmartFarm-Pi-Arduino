# 패치/배포 이력

각 차수별로 적용된 변경 사항을 정리한 문서입니다.  
상세 내역은 **`patch/`** 폴더의 차수별 파일(예: `patch/06.md`)을 참고하세요.

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

## 6차 배포 (그래프 맨 위 + X축 정리 + N·P·K)

- **웹 순서**
  - **그래프 섹션**을 **맨 위**로 이동 (헤더 다음 → 릴레이 → 스케줄)
- **X축**
  - 매 갱신 시 `scales.x.min = 0`, `scales.x.max = 399` 고정 → 끝없이 늘어나지 않음
  - **1시간 단위만 표시**: 정각(분=0)인 시점에만 라벨 표시, 나머지는 빈 문자열
- **N·P·K**
  - 센서 JSON에 `soil_N`, `soil_P`, `soil_K` 수치가 있으면 수신·저장·표시
  - **그래프 3개 추가**: N / P / K 각각 전용 차트, Y축 고정(예: 0~200)
- **수정 파일**: `PATCH.md`, `index.html`, `style.css`, `app.js`

---

## 7차 배포 (실시간·평균만 표시, 그래프 삭제)

- **웹**
  - **그래프 전부 제거**: Chart.js 스크립트·7개 canvas 삭제, 차트 관련 JS 제거
  - **토양 센서 섹션**: 온도·습도·EC·pH·N·P·K 7개 지표에 대해 **실시간값**과 **7일 평균**만 카드 형태로 표시
  - 같은 `/api/badge/history` 데이터로 마지막 1건 = 실시간, 전체 평균 = 7일 평균 계산
- **수정 파일**: `index.html`, `app.js`, `style.css`, `PATCH.md`, `patch/07.md`, `patch/README.md`

---

## 8차 배포 (요일별 스케줄 + 영문 요일 + 20개 확대 + 토양 센서 10분 송신)

- **아두이노**
  - 토양 센서 BADGE JSON 송신 주기: **3초 → 10분**(`sensorInterval = 600000` ms)으로 변경
- **스케줄 요일 표현**
  - `days` 필드를 `Mon,Tue,Wed,Thu,Fri,Sat,Sun` 영문 약어 콤마 구분으로 사용 (매일은 `daily`)
  - 기존 숫자 요일(0,1,2) 형식도 백엔드에서 그대로 인식, 저장 시 영문으로 정규화 가능
- **화면에서의 요일별 보기**
  - 채널별로 `All / Mon / Tue / Wed / Thu / Fri / Sat / Sun` 필터 버튼 제공
  - `All`: 전체 스케줄, 특정 요일: 해당 요일이 포함된 스케줄만 리스트에 표시
  - 스케줄 추가 시, 선택된 요일을 기본값으로 `days`에 채워 넣고 사용자가 필요 시 `Mon,Thu` 등으로 수정 가능
- **시간 형식 통일**
  - 스케줄 리스트 및 모달 표기를 24시간 `HH:MM`(예: `00:00`, `09:05`, `23:59`) 형식으로 통일
- **채널당 최대 스케줄 수 상향**
  - 채널당 스케줄 최대 개수를 10개 → **20개**로 확대 (`schedule_store.MAX_PER_CHANNEL`, 프론트 검증)
- **수정 파일**: `arduino/.../smart_farm_relay.ino`, `pi/schedule_store.py`, `pi/scheduler_service.py`, `pi/templates/index.html`, `pi/static/app.js`, `pi/static/style.css`, `PATCH.md`, `patch/08.md`, `patch/README.md`

---

## 9차 배포 (예정: 요일 체크박스 · NPK 웹 연동 · 카메라/드라이브 통합 · 웹 표시 개선)

- **스케줄 요일 설정형(체크식) 전환**
  - 스케줄 모달에서 요일을 텍스트로 입력(`daily`, `Mon,Tue,Wed` 등)하는 방식 대신
    `매일(daily)` 체크박스 + `Mon~Sun` 7개 요일 체크박스로 선택하는 UI로 변경
  - 저장 시 기존과 동일하게 `daily` 또는 `Mon,Tue,Wed` 형태의 문자열로 변환하여 백엔드와 호환 유지
- **RS485 NPK 값 웹 연동**
  - Halisense TH-EC-PH-NPK 센서에서 N·P·K(Modbus 레지스터, 예: 4/5/6) 값을 읽어
    아두이노 BADGE JSON에 `soil_N`, `soil_P`, `soil_K` 필드로 포함
  - 기존 Pi/Web 측 NPK 표시 로직(실시간/7일 평균)에 실제 센서 값이 반영되도록 검증
- **카메라 + Google Drive 업로드 양성화**
  - `/home/pi/camera_project/camera_capture.py + crontab + rclone` 구조를 SmartFarm 프로젝트의 공식 기능으로 문서화
  - rpicam-still 촬영 옵션, 로컬 저장 경로(`/home/pi/camera_project/photos`), rclone remote 이름(`ANJAEHUN_SMART_FARM`), 원격 폴더(`SmartFarmPhotos`), crontab 설정(10분마다 촬영/업로드)을 `patch/09.md` 및 README류에 명시
  - 업로드 성공 시 로컬 사진 파일을 **즉시 삭제**하여 라즈베리파이 저장 공간을 절약하는 정책 반영
  - 필요 시 `config.json`의 `camera` 섹션과 연동하는 방향 검토
- **웹 표시 개선**
  - 상단 토양 센서 카드와 스케줄 표 사이에 “카메라 촬영/업로드 상태” 표시 영역 추가  
    - 예: `00:00 촬영 및 드라이브 업로드 완료`, `00:10 촬영 실패`, `00:20 업로드 실패` 등
  - 스케줄 표의 시간/날짜 X축 텍스트를 한 줄에 보이도록 줄바꿈/레이아웃 조정 및 글자 크기 확대로 가독성 향상

---

## 10차 배포 (예정: 카메라 · 연결 개선 · 유지보수 · 웹 UI)

- **회차**: 이번 작업은 **10차**로 정리 (9차는 요일 체크박스·NPK·문서화 등 유지).
- **범위**: (1) 카메라 양성화 (2) 연결/알림 개선 (3) 유지보수(역추적 정리) (4) 웹 UI 업데이트.

- **1. 카메라**
  - **통합·양성화**: 경로를 알 수 없는 결과물(음성·음지)인 `/home/pi/camera_project` 등 GPT로 만든 별도 구조를 제거하고, SmartFarm 리포지토리 내 `pi/` 하위로 촬영·업로드 스크립트 편입. crontab/경로를 신규 구조 기준으로 정리하여 **양성(공식)** 구조만 유지.
  - **노출·조도**: 시간대(낮/저녁/야간)에 따라 `rpicam-still` 옵션(`--shutter`, `--gain`, `--ev`, `--awb`) 보정.
- **2. 연결 개선**
  - **Gmail 연결 끊김 알림 제거**: 현재 시리얼 미연결 시에는 동작하지 않는 `alert_email` 방식 제거.
  - **텔레그램 주기 현황**: 특정 시간마다(예: 1시간/6시간) 작동 현황(시리얼 연결 여부, 최근 센서·릴레이·카메라 상태 등)을 텔레그램으로 송신하는 구조로 전환.
- **3. 유지보수**
  - GPT로 추가된 업로드 주기·촬영 관련 코드·문서 역추적 후 정리: camera_project 의존 제거, 리포 내 한 구조만 유지.
- **4. 웹 UI**
  - **카메라 상태 섹션 위치**: 토양 센서 바로 아래, 릴레이 위로 이동 → “센서(토양·카메라) → 제어(릴레이) → 스케줄” 순서.
  - 카메라 상태 표시는 통합된 구조 기준 경로/API에 맞게 수정.

---

## 참고

- 배포 후 Pi: `cd /home/pi/SmartFarm-Pi-Arduino && git pull origin main`  
- 앱 재시작: `cd 26_2_24_01 && source venv/bin/activate && python3 pi/app.py`  
- 웹 캐시 반영: 브라우저 **Ctrl+F5** (강력 새로고침)
