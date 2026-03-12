# -*- coding: utf-8 -*-
"""
연결 끊김 감지 시 이메일 발송.
config.alert.email_enabled=True, smtp_* 및 to_email 설정 필요.
"""
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

_alert_sent = False


def send_disconnect_email(config):
    """config['alert'] 설정으로 '시리얼/아두이노 연결 끊김' 안내 메일 전송."""
    global _alert_sent
    cfg = config.get("alert") or {}
    if not cfg.get("email_enabled"):
        return False
    to_email = cfg.get("to_email", "").strip()
    if not to_email:
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "[스마트팜] 시리얼 연결 끊김 - 재부팅 권장"
        body = (
            "라즈베리파이 스마트팜에서 아두이노/시리얼 연결이 끊어진 것으로 감지되었습니다.\n\n"
            "재부팅 또는 시리얼 재연결을 권장합니다.\n"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))
        host = cfg.get("smtp_host", "smtp.gmail.com")
        port = int(cfg.get("smtp_port", 587))
        user = cfg.get("smtp_user", "")
        password = cfg.get("smtp_password", "")
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            if user and password:
                s.login(user, password)
            s.sendmail(user or "smartfarm@local", to_email, msg.as_string())
        _alert_sent = True
        return True
    except Exception as e:
        print("Alert email error:", e)
        return False


def check_disconnect_and_alert(config=None):
    """
    시리얼이 열려 있는데 last_activity 가 disconnect_seconds 초과면
    한 번만 이메일 발송. config 가 None 이면 config.json 에서 로드.
    """
    global _alert_sent
    import os
    import json
    import serial_relay
    if config is None:
        path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
    cfg = config.get("alert") or {}
    if not cfg.get("email_enabled") or _alert_sent:
        return
    if not serial_relay.is_open():
        return
    timeout = int(cfg.get("disconnect_seconds", 300))
    last = serial_relay.get_last_activity()
    if last > 0 and (time.time() - last) >= timeout:
        if send_disconnect_email(config):
            _alert_sent = True


def reset_alert_sent():
    """시리얼 재연결 후 호출하여 다음 끊김 시 다시 메일 보내도록."""
    global _alert_sent
    _alert_sent = False
