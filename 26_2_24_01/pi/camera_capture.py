# -*- coding: utf-8 -*-
"""
일정 시간에 따라 촬영 후 저장.
- 라즈베리파이: picamera2 또는 opencv(USB 캠) 사용 가능.
- config.json 의 camera.enabled, interval_seconds, save_dir 참고.
- 실행: python camera_capture.py once  → 1장 촬영
- 또는 cron/스케줄러에서 주기적으로 'python camera_capture.py once' 호출.
"""
import os
import json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def capture_once_picamera2(save_path):
    """Pi 공식 카메라 (picamera2)."""
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.start()
        cam.capture_file(save_path)
        cam.stop()
        return True
    except Exception as e:
        print("picamera2 error:", e)
        return False


def capture_once_opencv(save_path):
    """USB 웹캠 (opencv)."""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        cap.release()
        if ret:
            cv2.imwrite(save_path, frame)
            return True
        return False
    except Exception as e:
        print("opencv capture error:", e)
        return False


def main():
    import sys
    cfg = load_config().get("camera", {})
    save_dir = cfg.get("save_dir") or PHOTOS_DIR
    os.makedirs(save_dir, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.jpg")
    save_path = os.path.join(save_dir, filename)

    if "once" in (sys.argv[1:] or ["once"]):
        if capture_once_picamera2(save_path):
            print("Saved:", save_path)
        elif capture_once_opencv(save_path):
            print("Saved:", save_path)
        else:
            print("Capture failed (no camera backend available?)")


if __name__ == "__main__":
    main()
