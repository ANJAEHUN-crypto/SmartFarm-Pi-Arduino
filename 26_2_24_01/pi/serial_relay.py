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
_io_lock = threading.Lock()
_last_activity = 0.0  # 연결 끊김 감지용
_last_port = DEFAULT_PORT
_last_baud = DEFAULT_BAUD

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
            try:
                if _ser and _ser.is_open:
                    _ser.close()
            except Exception:
                pass
            _ser = None
            if _reader_running:
                time.sleep(0.05)
            break


def _clear_response_queue():
    while True:
        try:
            _response_queue.get_nowait()
        except Empty:
            break


def _reconnect():
    close()
    time.sleep(0.2)
    open(port=_last_port, baud=_last_baud)


def open(port=None, baud=None):
    global _ser, _reader_thread, _reader_running, _response_queue, _badge_lines, _last_port, _last_baud
    port = port or DEFAULT_PORT
    baud = baud or DEFAULT_BAUD
    _last_port = port
    _last_baud = baud
    if _ser and _ser.is_open:
        close()
    _ser = serial.Serial(port, baud, timeout=0.2, write_timeout=1.0)
    time.sleep(1.0)
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

def _write_read(line, expect_prefix=None, timeout=2.5, retries=2):
    global _ser, _response_queue
    with _io_lock:
        last_error = None
        for attempt in range(retries + 1):
            try:
                if not _ser or not _ser.is_open:
                    _reconnect()
                _clear_response_queue()
                _ser.write((line.strip() + "\n").encode())
                _ser.flush()
                deadline = time.time() + timeout
                while time.time() < deadline:
                    wait = max(0.1, deadline - time.time())
                    try:
                        reply = _response_queue.get(timeout=min(0.5, wait))
                    except Empty:
                        continue
                    if expect_prefix and not reply.startswith(expect_prefix):
                        continue
                    return reply
                last_error = RuntimeError("Serial response timeout")
            except Exception as e:
                last_error = e
            if attempt < retries:
                try:
                    _reconnect()
                except Exception as e:
                    last_error = e
                time.sleep(0.2)
        if last_error:
            raise last_error
        return None

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
    try:
        r = _write_read("STATE", "S ")
    except Exception:
        return None
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
    return _ser is not None and _ser.is_open and _reader_running
