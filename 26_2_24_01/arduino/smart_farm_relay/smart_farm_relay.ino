/*
 * 스마트팜 4ch 릴레이 제어 (아두이노 우노 R4 Wi-Fi)
 * USB 시리얼로 Pi와 통신
 * 1ch(LED1), 2ch(PUMP1), 3ch(LED2), 4ch(PUMP2) - NO 접점
 * 
 * 프로토콜: 한 줄 단위
 *   ON 1 ~ ON 4  : 해당 채널 ON
 *   OFF 1 ~ OFF 4 : 해당 채널 OFF
 *   STATE        : 현재 4채널 상태 응답 "S 0|1 0|1 0|1 0|1"
 */

const int RELAY_PINS[] = {2, 3, 4, 5};  // 1ch~4ch
const int N_CH = 4;
bool state[4] = {false, false, false, false};

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < N_CH; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);   // NO 접점: LOW=OFF
  }
}

void loop() {
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
