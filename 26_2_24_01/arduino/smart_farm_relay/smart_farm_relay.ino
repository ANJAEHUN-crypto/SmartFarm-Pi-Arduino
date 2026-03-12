/*
 * 스마트팜 4ch 릴레이 + RS485 Modbus 토양센서 (아두이노 우노 R4 Wi-Fi)
 * USB 시리얼: Pi와 통신 (릴레이 제어 + 센서 JSON 수신)
 * RS485: D6(RX), D7(TX), D8(DE) — Modbus 토양센서 (온도/습도/EC/pH)
 *
 * 릴레이: 1ch=D2, 2ch=D3, 3ch=D4, 4ch=D5 — NO 접점
 *
 * 프로토콜 (USB 시리얼): 한 줄 단위
 *   ON 1 ~ ON 4  / OFF 1 ~ OFF 4  / STATE → "S 0 1 0 1"
 * 센서 데이터: 3초마다 JSON 한 줄을 "BADGE " 접두사로 Serial 전송 → Pi/HiveMQ
 */

#include <SoftwareSerial.h>

#define RS485_RX 6
#define RS485_TX 7
#define RS485_DE 8

SoftwareSerial rs485(RS485_RX, RS485_TX);

const int RELAY_PINS[4] = {2, 3, 4, 5};
bool relayState[4] = {0, 0, 0, 0};

// Modbus RTU 요청 (슬레이브 0x01, 기능 0x03, 레지스터 읽기)
byte cmd_temp[] = {0x01, 0x03, 0x00, 0x01, 0x00, 0x01, 0xD5, 0xCA};
byte cmd_humi[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x84, 0x0A};
byte cmd_ec[]   = {0x01, 0x03, 0x00, 0x02, 0x00, 0x01, 0x25, 0xCA};
byte cmd_ph[]   = {0x01, 0x03, 0x00, 0x03, 0x00, 0x01, 0x74, 0x0A};

float soil_temperature = 0;
float soil_humidity = 0;
int soil_ec = 0;
float soil_ph = 0;

unsigned long sensorTimer = 0;
const unsigned long sensorInterval = 3000;

int readSensor(byte *cmd) {
  while (rs485.available()) rs485.read();

  digitalWrite(RS485_DE, HIGH);
  rs485.write(cmd, 8);
  rs485.flush();
  digitalWrite(RS485_DE, LOW);

  byte buf[7];
  int i = 0;
  unsigned long start = millis();

  while (millis() - start < 200) {
    if (rs485.available()) {
      buf[i++] = rs485.read();
      if (i == 7) break;
    }
  }

  if (i == 7) {
    int value = (int)buf[3] << 8 | buf[4];
    return value;
  }
  return -1;
}

void readAllSensors() {
  soil_temperature = readSensor(cmd_temp) / 10.0f;
  soil_humidity = readSensor(cmd_humi) / 10.0f;
  soil_ec = readSensor(cmd_ec);
  soil_ph = readSensor(cmd_ph) / 10.0f;

  // Pi가 "BADGE " 로 시작하는 줄만 배지/센서 데이터로 수집 → JSON 유지
  Serial.print("BADGE {\"status\":\"success\",");
  Serial.print("\"soil_temperature\":");
  Serial.print(soil_temperature);
  Serial.print(",\"soil_humidity\":");
  Serial.print(soil_humidity);
  Serial.print(",\"soil_EC\":");
  Serial.print(soil_ec);
  Serial.print(",\"soil_ph\":");
  Serial.print(soil_ph);
  Serial.println("}");
}

void handleSerial() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd.startsWith("ON ")) {
    int ch = cmd.substring(3).toInt();
    if (ch >= 1 && ch <= 4) {
      relayState[ch - 1] = 1;
      digitalWrite(RELAY_PINS[ch - 1], HIGH);
      Serial.println("OK");
    } else Serial.println("ERR");
  } else if (cmd.startsWith("OFF ")) {
    int ch = cmd.substring(4).toInt();
    if (ch >= 1 && ch <= 4) {
      relayState[ch - 1] = 0;
      digitalWrite(RELAY_PINS[ch - 1], LOW);
      Serial.println("OK");
    } else Serial.println("ERR");
  } else if (cmd == "STATE") {
    Serial.print("S ");
    for (int i = 0; i < 4; i++) {
      if (i) Serial.print(" ");
      Serial.print(relayState[i] ? 1 : 0);
    }
    Serial.println();
  } else {
    Serial.println("ERR");
  }
}

void setup() {
  Serial.begin(9600);
  rs485.begin(4800);  // Modbus 토양센서 보드레이트 (필요 시 9600 등으로 변경)

  pinMode(RS485_DE, OUTPUT);
  digitalWrite(RS485_DE, LOW);

  for (int i = 0; i < 4; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);
  }
}

void loop() {
  handleSerial();

  if (millis() - sensorTimer >= sensorInterval) {
    sensorTimer = millis();
    readAllSensors();
  }
}
