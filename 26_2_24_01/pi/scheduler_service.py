# -*- coding: utf-8 -*-
"""
스케줄 실행: 매분 현재 시각과 비교해 ON/OFF 전송.
채널당 20개, 작동 순서(시각)대로 정렬된 스케줄 적용.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import schedule_store
import serial_relay

scheduler = BackgroundScheduler()

def _today_str():
    return datetime.now().strftime("%Y-%m-%d")

def _weekday():
    """0=월, 6=일"""
    return datetime.now().weekday()

def _should_run_today(days):
    """days: 'daily' | '0,1,2' (월~일) | 'Mon,Tue,Wed' (영문). 0=월요일, 6=일요일."""
    if not days or str(days).strip() == "daily":
        return True
    today = _weekday()  # 0=Mon .. 6=Sun
    day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    try:
        for part in str(days).split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                if int(part) == today:
                    return True
            else:
                # 영문 요일 (대소문자 무시)
                for i, name in enumerate(day_names):
                    if part.lower() == name.lower():
                        if i == today:
                            return True
                        break
        return False
    except (ValueError, TypeError):
        return True

def _run_schedules():
    now = datetime.now()
    now_str = now.strftime("%H:%M")
    all_schedules = schedule_store.get_all()
    for ch, schedules in all_schedules.items():
        for s in schedules:
            on_t = s.get("on_time", "00:00")
            off_t = s.get("off_time", "00:00")
            if not _should_run_today(s.get("days")):
                continue
            if on_t == now_str:
                try:
                    if serial_relay.is_open():
                        serial_relay.relay_on(ch)
                except Exception:
                    pass
            if off_t == now_str:
                try:
                    if serial_relay.is_open():
                        serial_relay.relay_off(ch)
                except Exception:
                    pass

def _poll_badge():
    try:
        import badge_mqtt
        badge_mqtt.process_pending_badge_lines()
    except Exception:
        pass

def _camera_capture_job():
    """camera.enabled 이면 주기적으로 촬영·업로드."""
    try:
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if not config.get("camera", {}).get("enabled"):
            return
        import camera_capture
        camera_capture.main()
    except Exception as e:
        print("camera_capture job error:", e)

def _telegram_status_job():
    """telegram.enabled 이면 주기적으로 작동 현황 전송."""
    try:
        import telegram_status
        telegram_status.send_periodic_status()
    except Exception as e:
        print("telegram_status job error:", e)

def start_scheduler():
    scheduler.add_job(_run_schedules, IntervalTrigger(minutes=1), id="relay_schedule")
    scheduler.add_job(_poll_badge, IntervalTrigger(seconds=1), id="badge_poll")
    # 카메라: 10분(600초) 주기 또는 config camera.interval_seconds
    try:
        import json, os
        path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        interval_sec = 600
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                interval_sec = max(60, (json.load(f).get("camera") or {}).get("interval_seconds", 600))
        scheduler.add_job(_camera_capture_job, IntervalTrigger(seconds=interval_sec), id="camera_capture")
    except Exception:
        scheduler.add_job(_camera_capture_job, IntervalTrigger(minutes=10), id="camera_capture")
    # 텔레그램: config telegram.interval_minutes (기본 10)
    try:
        import json, os
        path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        interval_min = 10
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                interval_min = max(5, (json.load(f).get("telegram") or {}).get("interval_minutes", 10))
        scheduler.add_job(_telegram_status_job, IntervalTrigger(minutes=interval_min), id="telegram_status")
    except Exception:
        scheduler.add_job(_telegram_status_job, IntervalTrigger(minutes=10), id="telegram_status")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown(wait=False)
