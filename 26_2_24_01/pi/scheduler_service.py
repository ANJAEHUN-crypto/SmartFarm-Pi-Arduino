# -*- coding: utf-8 -*-
"""
스케줄 실행: 매분 현재 시각과 비교해 ON/OFF 전송.
채널당 10개, 작동 순서(시각)대로 정렬된 스케줄 적용.
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
    if not days or days == "daily":
        return True
    try:
        allowed = [int(x.strip()) for x in str(days).split(",")]
        return _weekday() in allowed
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

def start_scheduler():
    scheduler.add_job(_run_schedules, IntervalTrigger(minutes=1), id="relay_schedule")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown(wait=False)
