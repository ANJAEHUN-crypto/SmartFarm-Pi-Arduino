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

_mqtt_client = None
_mqtt_enabled = False
_mqtt_topic = "smartfarm/badge"


def _load_history():
    if os.path.exists(BADGE_JSON):
        try:
            with open(BADGE_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
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
        item = {"t": ts, "raw": raw}
        history.append(item)
        out.append(item)
        if _mqtt_enabled and _mqtt_client:
            try:
                # 센서값이 JSON 문자열이면 합쳐서, 아니면 t+raw 로 퍼블리시
                payload_obj = {"t": ts}
                raw_stripped = raw.strip()
                if raw_stripped.startswith("{") or raw_stripped.startswith("["):
                    try:
                        parsed = json.loads(raw_stripped)
                        if isinstance(parsed, dict):
                            payload_obj.update(parsed)
                        else:
                            payload_obj["raw"] = parsed
                    except (ValueError, TypeError):
                        payload_obj["raw"] = raw
                else:
                    payload_obj["raw"] = raw
                payload = json.dumps(payload_obj, ensure_ascii=False)
                _mqtt_client.publish(_mqtt_topic, payload, qos=0)
            except Exception:
                pass
    _save_history(history)
    return out


def get_badge_history(limit=100):
    """그래프/API용: 최근 배지 기록 반환."""
    history = _load_history()
    return history[-limit:]
