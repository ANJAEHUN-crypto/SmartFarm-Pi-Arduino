# -*- coding: utf-8 -*-
"""
스마트팜 웹 서버 (라즈베리파이)
- 릴레이 원격 ON/OFF
- 채널당 스케줄 최대 20개, 작동 순서 정렬
"""
import os
import json
from flask import Flask, request, jsonify, send_from_directory, render_template

import serial_relay
import schedule_store
import scheduler_service
import badge_mqtt

app = Flask(__name__, static_folder="static", template_folder="templates")

# 설정 (config.json 있으면 로드)
CONFIG = {}
config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
SERIAL_PORT = CONFIG.get("serial", {}).get("port") or serial_relay.DEFAULT_PORT
SERIAL_BAUD = CONFIG.get("serial", {}).get("baud") or serial_relay.DEFAULT_BAUD
badge_mqtt.init_mqtt(CONFIG)


@app.route("/")
def index():
    return render_template("index.html")


# ---------- 릴레이 API ----------
@app.route("/api/serial/open", methods=["POST"])
def api_serial_open():
    try:
        port = request.json.get("port", SERIAL_PORT) if request.json else SERIAL_PORT
        baud = request.json.get("baud", SERIAL_BAUD) if request.json else SERIAL_BAUD
        serial_relay.open(port=port, baud=baud)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/serial/close", methods=["POST"])
def api_serial_close():
    try:
        serial_relay.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/serial/status")
def api_serial_status():
    return jsonify({"open": serial_relay.is_open()})


@app.route("/api/relay/on/<int:ch>", methods=["POST"])
def api_relay_on(ch):
    if ch < 1 or ch > 4:
        return jsonify({"ok": False, "error": "channel 1-4"}), 400
    try:
        ok = serial_relay.relay_on(ch)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/relay/off/<int:ch>", methods=["POST"])
def api_relay_off(ch):
    if ch < 1 or ch > 4:
        return jsonify({"ok": False, "error": "channel 1-4"}), 400
    try:
        ok = serial_relay.relay_off(ch)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/relay/state")
def api_relay_state():
    try:
        state = serial_relay.get_state()
        if state is None:
            return jsonify({"ok": False, "error": "no response"}), 500
        return jsonify({"ok": True, "state": state})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------- 배지(RS485) API (그래프용) ----------
@app.route("/api/badge/history")
def api_badge_history():
    limit = request.args.get("limit", 2000, type=int)
    days = request.args.get("days", 7, type=int)  # 기본 주간(7일)
    if limit <= 0 or limit > 5000:
        limit = 2000
    if days <= 0 or days > 30:
        days = 7
    try:
        data = badge_mqtt.get_badge_history(limit=limit, days=days)
        return jsonify({"ok": True, "history": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/camera/status")
def api_camera_status():
    """통합 카메라 모듈 기준 최근 촬영/업로드 상태 (config camera.save_dir)."""
    try:
        import camera_capture
        photos_dir = camera_capture.get_photos_dir(CONFIG)
        status_file = camera_capture.get_status_path(CONFIG)
        if os.path.exists(status_file):
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify({"ok": True, "source": "status_file", "data": data})
        if not os.path.isdir(photos_dir):
            return jsonify({"ok": True, "source": "none", "message": "카메라 저장 폴더가 없습니다."})
        files = [os.path.join(photos_dir, f) for f in os.listdir(photos_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not files:
            return jsonify({"ok": True, "source": "none", "message": "저장된 촬영 이미지가 없습니다."})
        latest = max(files, key=os.path.getmtime)
        ts = os.path.getmtime(latest)
        from datetime import datetime
        dt = datetime.fromtimestamp(ts)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        msg = "마지막 촬영 파일: {} (저장 시각: {})".format(os.path.basename(latest), time_str)
        return jsonify({"ok": True, "source": "files", "message": msg, "time": time_str})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------- 스케줄 API (채널당 20개, 작동 순서 정렬) ----------
@app.route("/api/schedules", methods=["GET"])
def api_schedules_get():
    data = schedule_store.get_all()
    return jsonify({"ok": True, "schedules": data})


@app.route("/api/schedules", methods=["POST"])
def api_schedules_add():
    d = request.json or {}
    ch = d.get("channel")
    on_time = d.get("on_time", "09:00")
    off_time = d.get("off_time", "18:00")
    days = d.get("days", "daily")
    if ch not in (1, 2, 3, 4):
        return jsonify({"ok": False, "error": "channel 1-4"}), 400
    ok, result = schedule_store.add(ch, on_time, off_time, days)
    if not ok:
        return jsonify({"ok": False, "error": result}), 400
    return jsonify({"ok": True, "schedule": result})


@app.route("/api/schedules/<int:ch>/<int:index>", methods=["DELETE"])
def api_schedules_delete(ch, index):
    if ch not in (1, 2, 3, 4):
        return jsonify({"ok": False, "error": "channel 1-4"}), 400
    ok = schedule_store.delete(ch, index)
    return jsonify({"ok": ok})


@app.route("/api/schedules/<int:ch>/<int:index>", methods=["PUT"])
def api_schedules_update(ch, index):
    d = request.json or {}
    on_time = d.get("on_time", "09:00")
    off_time = d.get("off_time", "18:00")
    days = d.get("days", "daily")
    if ch not in (1, 2, 3, 4):
        return jsonify({"ok": False, "error": "channel 1-4"}), 400
    ok, result = schedule_store.update(ch, index, on_time, off_time, days)
    if not ok:
        return jsonify({"ok": False, "error": result}), 400
    return jsonify({"ok": True, "schedule": result})


def main():
    # config에 포트가 있으면 시리얼 자동 연결 시도
    if CONFIG.get("serial", {}).get("port"):
        try:
            serial_relay.open(port=SERIAL_PORT, baud=SERIAL_BAUD)
        except Exception:
            pass
    scheduler_service.start_scheduler()
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        scheduler_service.stop_scheduler()
        badge_mqtt.close_mqtt()
        serial_relay.close()


if __name__ == "__main__":
    main()
