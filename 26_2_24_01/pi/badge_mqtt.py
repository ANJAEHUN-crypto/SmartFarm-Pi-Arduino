# -*- coding: utf-8 -*-
"""
RS485 배지 데이터 수신 → HiveMQ(MQTT) 퍼블리시 + 로컬 저장 (그래프/API용)
serial_relay.get_pending_badge_lines() 를 주기적으로 호출하여 처리.
"""
import json
import os
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BADGE_JSON = os.path.join(DATA_DIR, "badge_history.json")
MAX_HISTORY = 500
SECONDS_PER_DAY = 86400
WEEK_DAYS = 7

_mqtt_client = None
_mqtt_enabled = False
_mqtt_topic = "smartfarm/badge"


SENSOR_RANGES = {
    "soil_temperature": (-10.0, 80.0),
    "soil_humidity": (0.0, 100.0),
    "soil_EC": (0.0, 20000.0),
    "soil_ph": (0.0, 14.0),
    "soil_N": (0.0, 2000.0),
    "soil_P": (0.0, 2000.0),
    "soil_K": (0.0, 2000.0),
}


def _sanitize_sensor_payload(parsed):
    """센서 범위를 벗어난 값을 제거하고, 유효 센서값이 없으면 None 반환."""
    if not isinstance(parsed, dict):
        return None
    out = dict(parsed)
    valid_count = 0
    for key, (min_v, max_v) in SENSOR_RANGES.items():
        if key not in out:
            continue
        try:
            v = float(out[key])
        except (TypeError, ValueError):
            out.pop(key, None)
            continue
        if v < min_v or v > max_v:
            out.pop(key, None)
            continue
        if key in ("soil_EC", "soil_N", "soil_P", "soil_K"):
            out[key] = int(round(v))
        else:
            out[key] = round(v, 2)
        valid_count += 1
    if valid_count == 0:
        return None
    out["status"] = "success"
    return out


def _load_history():
    if os.path.exists(BADGE_JSON):
        try:
            with open(BADGE_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_history(history):
    """7일 초과 데이터 제거 후 저장."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        cutoff = time.time() - (WEEK_DAYS * SECONDS_PER_DAY)
        history = [x for x in history if x.get("t", 0) >= cutoff]
        with open(BADGE_JSON, "w", encoding="utf-8") as f:
            json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=0)
    except Exception:
        pass


def init_mqtt(config):
    """config['mqtt'] 에서 설정 로드. enabled=True 이면 MQTT 클라이언트 연결 (HiveMQ Cloud: 8883, TLS, 인증)."""
    global _mqtt_client, _mqtt_enabled, _mqtt_topic
    mqtt_cfg = config.get("mqtt") or {}
    _mqtt_enabled = mqtt_cfg.get("enabled", False)
    _mqtt_topic = mqtt_cfg.get("topic", "greenbean")
    if not _mqtt_enabled:
        return
    try:
        import paho.mqtt.client as mqtt
        broker = mqtt_cfg.get("broker", "broker.hivemq.com")
        port = int(mqtt_cfg.get("port", 1883))
        client_id = mqtt_cfg.get("client_id", "smartfarm-pi")
        use_tls = mqtt_cfg.get("tls", port == 8883)
        username = mqtt_cfg.get("username", "")
        password = mqtt_cfg.get("password", "")

        _mqtt_client = mqtt.Client(client_id=client_id)
        if use_tls:
            _mqtt_client.tls_set()
        if username:
            _mqtt_client.username_pw_set(username, password or None)
        _mqtt_client.connect(broker, port, keepalive=60)
        _mqtt_client.loop_start()
    except Exception as e:
        _mqtt_enabled = False
        _mqtt_client = None
        print("MQTT init error:", e)


def close_mqtt():
    global _mqtt_client, _mqtt_enabled
    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception:
            pass
        _mqtt_client = None
    _mqtt_enabled = False


def process_pending_badge_lines(config=None):
    """
    serial_relay 에서 대기 중인 배지 줄을 가져와 MQTT 퍼블리시 + 로컬 저장.
    config 가 None 이면 MQTT 퍼블리시 건너뜀 (이미 init_mqtt 로 설정된 경우 사용).
    """
    import serial_relay
    if not serial_relay.is_open():
        return []
    lines = serial_relay.get_pending_badge_lines()
    if not lines:
        return []
    history = _load_history()
    out = []
    for raw in lines:
        ts = time.time()
        payload_obj = None
        raw_to_store = raw
        raw_stripped = raw.strip()
        if raw_stripped.startswith("{") or raw_stripped.startswith("["):
            try:
                parsed = json.loads(raw_stripped)
                payload_obj = _sanitize_sensor_payload(parsed)
                if payload_obj is None:
                    continue
                raw_to_store = json.dumps(payload_obj, ensure_ascii=False)
            except (ValueError, TypeError):
                payload_obj = None
        item = {"t": ts, "raw": raw_to_store}
        history.append(item)
        out.append(item)
        if _mqtt_enabled and _mqtt_client:
            try:
                # 센서값이 JSON이면 검증된 값만 퍼블리시
                payload = json.dumps(
                    {"t": ts, **payload_obj} if isinstance(payload_obj, dict) else {"t": ts, "raw": raw_to_store},
                    ensure_ascii=False,
                )
                _mqtt_client.publish(_mqtt_topic, payload, qos=0)
            except Exception:
                pass
    _save_history(history)
    return out


def get_badge_history(limit=100, days=None):
    """그래프/API용: 최근 배지 기록 반환. days=7 이면 최근 7일만."""
    history = _load_history()
    if days is not None and days > 0:
        cutoff = time.time() - (days * SECONDS_PER_DAY)
        history = [x for x in history if x.get("t", 0) >= cutoff]
    return history[-limit:]
