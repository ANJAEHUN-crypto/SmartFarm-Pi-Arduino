# -*- coding: utf-8 -*-
"""
특정 주기마다 스마트팜 작동 현황을 텔레그램으로 전송.
config.json 의 telegram.enabled, bot_token, chat_id, interval_minutes 사용.
"""
import os
import json
import urllib.request
import urllib.error

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def send_telegram_message(bot_token, chat_id, text):
    """텍스트 메시지 전송. 성공 시 True."""
    url = "https://api.telegram.org/bot{}/sendMessage".format(bot_token)
    data = {"chat_id": chat_id, "text": text[:4096], "disable_web_page_preview": True}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError) as e:
        print("Telegram send error:", e)
        return False


def build_status_message(config=None):
    """
    현재 작동 현황 문자열 조립.
    시리얼 연결, 릴레이 상태, 각종 센서값, 사진 구글 드라이브 업로드 여부를 포함.
    """
    if config is None:
        config = load_config()
    lines = ["[스마트팜 작동 현황 (10분 단위)]"]

    try:
        import serial_relay
        if serial_relay.is_open():
            lines.append("• 시리얼: 연결됨")
            last = serial_relay.get_last_activity()
            if last and last > 0:
                import time
                ago = int(time.time() - last)
                if ago < 3600:
                    lines.append("  마지막 활동: {}분 전".format(ago // 60))
                else:
                    lines.append("  마지막 활동: {}시간 전".format(ago // 3600))
        else:
            lines.append("• 시리얼: 연결 안 됨")
    except Exception:
        lines.append("• 시리얼: 확인 불가")

    # 릴레이: 웹과 동일하게 1ch LED1, 2ch PUMP1, 3ch LED2, 4ch PUMP2 / ON·OFF
    try:
        import serial_relay
        state = serial_relay.get_state()
        if state is not None:
            labels = ["LED1", "PUMP1", "LED2", "PUMP2"]
            parts = []
            for i, name in enumerate(labels):
                if i < len(state):
                    parts.append("{} {}".format(name, "ON" if state[i] else "OFF"))
            lines.append("• 릴레이: " + ", ".join(parts))
        else:
            lines.append("• 릴레이: 상태 없음")
    except Exception:
        lines.append("• 릴레이: 확인 불가")

    # 센서: badge_history는 { t, raw } 저장 → raw 문자열을 파싱해 soil_* 추출 (웹과 동일)
    try:
        import badge_mqtt
        history = badge_mqtt.get_badge_history(limit=1, days=7)
        if history:
            d = history[-1]
            raw = d.get("raw")
            if isinstance(raw, str) and raw.strip().startswith("{"):
                try:
                    parsed = json.loads(raw)
                except (ValueError, TypeError):
                    parsed = {}
            elif isinstance(raw, dict):
                parsed = raw
            else:
                parsed = {}
            parts = []
            for key, label in [
                ("soil_temperature", "온도"),
                ("soil_humidity", "습도"),
                ("soil_EC", "EC"),
                ("soil_ph", "pH"),
                ("soil_N", "N"),
                ("soil_P", "P"),
                ("soil_K", "K"),
            ]:
                v = parsed.get(key)
                if v is not None:
                    parts.append("{} {}".format(label, v))
            if parts:
                lines.append("• 센서: " + ", ".join(parts))
            else:
                lines.append("• 센서: 값 없음")
        else:
            lines.append("• 센서: 데이터 없음")
    except Exception:
        lines.append("• 센서: 확인 불가")

    # 카메라: camera_status.json message
    try:
        import camera_capture
        status_path = camera_capture.get_status_path(config)
        if os.path.exists(status_path):
            with open(status_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lines.append("• 카메라: {}".format(data.get("message", "-")))
        else:
            lines.append("• 카메라: 상태 없음")
    except Exception:
        lines.append("• 카메라: 확인 불가")

    from datetime import datetime
    lines.append("")
    lines.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    return "\n".join(lines)


def send_periodic_status(config=None):
    """설정이 켜져 있으면 현황 메시지 조립 후 텔레그램 전송."""
    if config is None:
        config = load_config()
    tg = config.get("telegram") or {}
    if not tg.get("enabled"):
        return
    token = (tg.get("bot_token") or "").strip()
    chat_id = (tg.get("chat_id") or "").strip()
    if not token or not chat_id:
        return
    text = build_status_message(config)
    send_telegram_message(token, chat_id, text)
