/*
 * 스마트팜 4ch 릴레이 + RS485 Modbus 토양센서 (아두이노 우노 R4 Wi-Fi)
 * USB 시리얼: Pi와 통신 (릴레이 제어 + 센서 JSON 수신)
 * RS485: D6(RX), D7(TX), D8(DE) — Modbus 토양센서 (온도/습도/EC/pH)
 *
 * 릴레이: 1ch=D2, 2ch=D3, 3ch=D4, 4ch=D5 — NO 접점
 *
 * 프로토콜 (USB 시리얼): 한 줄 단위
 *   ON 1 ~ ON 4  / OFF 1 ~ OFF 4  / STATE → "S 0 1 0 1"
 * 센서 데이터: 10분마다 JSON 한 줄을 "BADGE " 접두사로 Serial 전송 → Pi/HiveMQ
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
int soil_N = 0;
int soil_P = 0;
int soil_K = 0;

unsigned long sensorTimer = 0;
const unsigned long sensorInterval = 600000;  // 10분 = 10 * 60 * 1000 ms

// Modbus CRC16 계산 (표준 다항식 0xA001)
unsigned int modbusCRC16(byte *buf, int len) {
  unsigned int crc = 0xFFFF;
  for (int pos = 0; pos < len; pos++) {
    crc ^= (unsigned int)buf[pos];
    for (int i = 0; i < 8; i++) {
      if (crc & 0x0001) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

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

int readRegister(unsigned int regAddr) {
  byte cmd[8];
  cmd[0] = 0x01;                    // 슬레이브 주소
  cmd[1] = 0x03;                    // 기능 코드 (Holding Register 읽기)
  cmd[2] = highByte(regAddr);       // 시작 레지스터 주소 High
  cmd[3] = lowByte(regAddr);        // 시작 레지스터 주소 Low
  cmd[4] = 0x00;                    // 레지스터 개수 High
  cmd[5] = 0x01;                    // 레지스터 개수 Low (1개)
  unsigned int crc = modbusCRC16(cmd, 6);
  cmd[6] = lowByte(crc);
  cmd[7] = highByte(crc);
  return readSensor(cmd);
}

void readAllSensors() {
  soil_temperature = readSensor(cmd_temp) / 10.0f;
  soil_humidity = readSensor(cmd_humi) / 10.0f;
  soil_ec = readSensor(cmd_ec);
  soil_ph = readSensor(cmd_ph) / 10.0f;

  // Halisense TH-EC-PH-NPK 센서의 N/P/K 레지스터는 장치 매뉴얼 기준으로 조정 필요
  int nVal = readRegister(4);  // 예: 레지스터 4 = N
  int pVal = readRegister(5);  // 예: 레지스터 5 = P
  int kVal = readRegister(6);  // 예: 레지스터 6 = K
  if (nVal >= 0) soil_N = nVal;
  if (pVal >= 0) soil_P = pVal;
  if (kVal >= 0) soil_K = kVal;

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
  Serial.print(",\"soil_N\":");
  Serial.print(soil_N);
  Serial.print(",\"soil_P\":");
  Serial.print(soil_P);
  Serial.print(",\"soil_K\":");
  Serial.print(soil_K);
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
