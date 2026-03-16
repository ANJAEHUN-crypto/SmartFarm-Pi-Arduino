# -*- coding: utf-8 -*-
"""
채널당 최대 20개 스케줄 저장/로드. 작동 순서(시작 시각) 기준 정렬.
형식: { "channel": 1~4, "on_time": "HH:MM", "off_time": "HH:MM", "days": "0-6" 또는 "daily" }
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SCHEDULES_FILE = os.path.join(DATA_DIR, "schedules.json")
MAX_PER_CHANNEL = 20

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load_raw():
    _ensure_data_dir()
    if not os.path.exists(SCHEDULES_FILE):
        return {"1": [], "2": [], "3": [], "4": []}
    with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_raw(data):
    _ensure_data_dir()
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _sort_schedules(schedules):
    """시작 시각(on_time) 기준 정렬."""
    def key(s):
        return s.get("on_time", "00:00")
    return sorted(schedules, key=key)

def get_all():
    raw = _load_raw()
    out = {}
    for ch in ("1", "2", "3", "4"):
        lst = raw.get(ch, [])
        if not isinstance(lst, list):
            lst = []
        out[int(ch)] = _sort_schedules(lst)[:MAX_PER_CHANNEL]
    return out

def get_channel(channel):
    ch = str(channel)
    if ch not in ("1", "2", "3", "4"):
        return []
    raw = _load_raw()
    lst = raw.get(ch, [])
    return _sort_schedules(lst)[:MAX_PER_CHANNEL]

def add(channel, on_time, off_time, days="daily"):
    """on_time, off_time: "HH:MM". days: "daily" or "0,1,2,3,4,5,6" (월~일)."""
    ch = str(channel)
    if ch not in ("1", "2", "3", "4"):
        return False, "Invalid channel"
    raw = _load_raw()
    lst = raw.get(ch, [])
    if len(lst) >= MAX_PER_CHANNEL:
        return False, "Max 20 schedules per channel"
    entry = {
        "channel": int(channel),
        "on_time": on_time,
        "off_time": off_time,
        "days": days,
    }
    lst.append(entry)
    raw[ch] = _sort_schedules(lst)
    _save_raw(raw)
    return True, entry

def delete(channel, index):
    """index: 0-based in sorted list."""
    ch = str(channel)
    if ch not in ("1", "2", "3", "4"):
        return False
    raw = _load_raw()
    lst = raw.get(ch, [])
    lst = _sort_schedules(lst)
    if index < 0 or index >= len(lst):
        return False
    lst.pop(index)
    raw[ch] = lst
    _save_raw(raw)
    return True

def update(channel, index, on_time, off_time, days="daily"):
    ch = str(channel)
    if ch not in ("1", "2", "3", "4"):
        return False, "Invalid channel"
    raw = _load_raw()
    lst = raw.get(ch, [])
    lst = _sort_schedules(lst)
    if index < 0 or index >= len(lst):
        return False, "Invalid index"
    lst[index] = {
        "channel": int(channel),
        "on_time": on_time,
        "off_time": off_time,
        "days": days,
    }
    raw[ch] = _sort_schedules(lst)
    _save_raw(raw)
    return True, lst[index]
