# -*- coding: utf-8 -*-
"""
아두이노 4ch 릴레이 시리얼 제어 + RS485 배지 데이터 수신
프로토콜: ON 1~4 / OFF 1~4 / STATE
아두이노에서 "BADGE " 접두사로 오는 줄은 배지 데이터로 수집 (get_pending_badge_lines)
"""
import serial
import time
import os
import threading
from queue import Queue, Empty

# Windows: COM3, COM4 등 / Linux(Pi): /dev/ttyACM0, /dev/ttyUSB0
DEFAULT_PORT = "COM3" if os.name == "nt" else "/dev/ttyACM0"
DEFAULT_BAUD = 9600

_ser = None
_reader_thread = None
_reader_running = False
_response_queue = Queue()
_badge_lines = []
_badge_lock = threading.Lock()
_last_activity = 0.0  # 연결 끊김 감지용

def _update_activity():
    global _last_activity
    import time
    _last_activity = time.time()

def get_last_activity():
    """연결 끊김 감지용: 마지막으로 시리얼에서 데이터를 받은 시각 (Unix timestamp)."""
    return _last_activity

def _serial_reader():
    global _ser, _reader_running, _response_queue, _badge_lines, _badge_lock
    while _reader_running and _ser and _ser.is_open:
        try:
            line = _ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("BADGE "):
                with _badge_lock:
                    _badge_lines.append(line[6:].strip())  # "BADGE " 제거
                _update_activity()
            else:
                _response_queue.put(line)
                _update_activity()
        except Exception:
            if _reader_running:
                time.sleep(0.05)
            break

def open(port=None, baud=None):
    global _ser, _reader_thread, _reader_running, _response_queue, _badge_lines
    port = port or DEFAULT_PORT
    baud = baud or DEFAULT_BAUD
    if _ser and _ser.is_open:
        close()
    _ser = serial.Serial(port, baud, timeout=0.2)
    time.sleep(0.1)
    _update_activity()
    _reader_running = True
    _response_queue = Queue()
    with _badge_lock:
        _badge_lines = []
    _reader_thread = threading.Thread(target=_serial_reader, daemon=True)
    _reader_thread.start()

def close():
    global _ser, _reader_thread, _reader_running
    _reader_running = False
    if _reader_thread:
        _reader_thread.join(timeout=0.5)
        _reader_thread = None
    if _ser and _ser.is_open:
        try:
            _ser.close()
        except Exception:
            pass
    _ser = None

def _write_read(line, expect_prefix=None):
    global _ser, _response_queue
    if not _ser or not _ser.is_open:
        raise RuntimeError("Serial not open")
    _ser.write((line.strip() + "\n").encode())
    time.sleep(0.05)
    try:
        reply = _response_queue.get(timeout=0.5)
    except Empty:
        return None
    if expect_prefix and not reply.startswith(expect_prefix):
        return None
    return reply

def get_pending_badge_lines():
    """RS485에서 수신한 배지 데이터 줄 목록을 반환하고 버퍼 비움."""
    with _badge_lock:
        out = list(_badge_lines)
        _badge_lines.clear()
    return out

def relay_on(ch):
    """ch: 1~4"""
    if ch not in (1, 2, 3, 4):
        return False
    r = _write_read("ON %d" % ch)
    return r == "OK"

def relay_off(ch):
    """ch: 1~4"""
    if ch not in (1, 2, 3, 4):
        return False
    r = _write_read("OFF %d" % ch)
    return r == "OK"

def get_state():
    """Returns [bool, bool, bool, bool] for ch1~4 or None on error."""
    r = _write_read("STATE", "S ")
    if not r or not r.startswith("S "):
        return None
    parts = r[2:].split()
    if len(parts) != 4:
        return None
    try:
        return [int(x) == 1 for x in parts]
    except ValueError:
        return None

def is_open():
    return _ser is not None and _ser.is_open
