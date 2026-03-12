# -*- coding: utf-8 -*-
"""
아두이노 4ch 릴레이 시리얼 제어
프로토콜: ON 1~4 / OFF 1~4 / STATE
"""
import serial
import time
import os

# Windows: COM3, COM4 등 / Linux(Pi): /dev/ttyACM0, /dev/ttyUSB0
DEFAULT_PORT = "COM3" if os.name == "nt" else "/dev/ttyACM0"
DEFAULT_BAUD = 9600

_ser = None

def open(port=None, baud=None):
    global _ser
    port = port or DEFAULT_PORT
    baud = baud or DEFAULT_BAUD
    if _ser and _ser.is_open:
        try:
            _ser.close()
        except Exception:
            pass
    _ser = serial.Serial(port, baud, timeout=0.5)
    time.sleep(0.1)

def close():
    global _ser
    if _ser and _ser.is_open:
        try:
            _ser.close()
        except Exception:
            pass
    _ser = None

def _write_read(line, expect_prefix=None):
    global _ser
    if not _ser or not _ser.is_open:
        raise RuntimeError("Serial not open")
    _ser.reset_input_buffer()
    _ser.write((line.strip() + "\n").encode())
    time.sleep(0.05)
    reply = _ser.readline().decode().strip()
    if expect_prefix and not reply.startswith(expect_prefix):
        return None
    return reply

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
