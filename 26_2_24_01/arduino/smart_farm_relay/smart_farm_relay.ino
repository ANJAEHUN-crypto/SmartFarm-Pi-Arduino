/*
 * 스마트팜 4ch 릴레이 제어 + RS485 수신 (아두이노 우노 R4 Wi-Fi)
 * USB 시리얼: Pi와 통신 (릴레이 제어)
 * RS485: D6(RX), D7(TX), D8(DE/RE) — 배지 등 센서 데이터 수신 → Pi로 전달
 *
 * 릴레이: 1ch(LED1)=D2, 2ch(PUMP1)=D3, 3ch(LED2)=D4, 4ch(PUMP2)=D5 — NO 접점
 *
 * 프로토콜 (USB 시리얼): 한 줄 단위
 *   ON 1 ~ ON 4  : 해당 채널 ON
 *   OFF 1 ~ OFF 4 : 해당 채널 OFF
 *   STATE        : 현재 4채널 상태 응답 "S 0|1 0|1 0|1 0|1"
 * Pi로 전달: RS485에서 수신한 줄은 "BADGE " 접두사로 Serial에 출력 (예: BADGE id=123,t=...)
 */

#include <SoftwareSerial.h>

const int RELAY_PINS[] = {2, 3, 4, 5};  // 1ch~4ch (D2~D5)
const int RS485_RX = 6;   // RS485 RO → D6
const int RS485_TX = 7;   // RS485 DI → D7
const int RS485_DE_RE = 8; // RS485 DE,RE → D8 (LOW=수신, HIGH=송신)
const int N_CH = 4;
bool state[4] = {false, false, false, false};

SoftwareSerial rs485(RS485_RX, RS485_TX); // RX, TX

void setup() {
  Serial.begin(9600);
  rs485.begin(9600);
  pinMode(RS485_DE_RE, OUTPUT);
  digitalWrite(RS485_DE_RE, LOW);  // 기본 수신 모드
  for (int i = 0; i < N_CH; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);   // NO 접점: LOW=OFF
  }
}

void loop() {
  // RS485 수신 → Pi로 전달 (한 줄 단위)
  if (rs485.available()) {
    String line = rs485.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      Serial.print("BADGE ");
      Serial.println(line);
    }
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    if (line.startsWith("ON ")) {
      int ch = line.substring(3).toInt();
      if (ch >= 1 && ch <= 4) {
        state[ch - 1] = true;
        digitalWrite(RELAY_PINS[ch - 1], HIGH);
        Serial.println("OK");
      } else Serial.println("ERR");
    } else if (line.startsWith("OFF ")) {
      int ch = line.substring(4).toInt();
      if (ch >= 1 && ch <= 4) {
        state[ch - 1] = false;
        digitalWrite(RELAY_PINS[ch - 1], LOW);
        Serial.println("OK");
      } else Serial.println("ERR");
    } else if (line == "STATE") {
      Serial.print("S ");
      for (int i = 0; i < N_CH; i++) {
        if (i) Serial.print(" ");
        Serial.print(state[i] ? 1 : 0);
      }
      Serial.println();
    } else {
      Serial.println("ERR");
    }
  }
}
