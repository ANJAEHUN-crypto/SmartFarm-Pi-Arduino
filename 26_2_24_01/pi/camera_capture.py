# -*- coding: utf-8 -*-
"""
카메라 촬영·저장·업로드 (10차 통합).
- rpicam-still 우선 (시간대별 노출 보정), picamera2/opencv 폴백.
- config.json camera: enabled, interval_seconds, save_dir, rclone_remote, rclone_path, delete_after_upload.
- 실행: python camera_capture.py once  → 1장 촬영 후 옵션에 따라 rclone 업로드.
- 스케줄러 또는 cron에서 주기적으로 'python camera_capture.py once' 호출.
"""
import os
import json
import subprocess
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
DEFAULT_PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
STATUS_FILENAME = "camera_status.json"
EXPOSURE_SETTINGS_FILENAME = "camera_exposure.json"

DEFAULT_EXPOSURE = {
    "day": {"shutter": 3000, "gain": 1.0, "ev": -2, "awb": "auto"},
    "evening": {"shutter": 33000, "gain": 1.5, "ev": 1, "awb": "fluorescent"},
    "night": {"shutter": 66000, "gain": 2.0, "ev": 2, "awb": "incandescent"},
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_photos_dir(config=None):
    """촬영 저장 디렉터리 (절대 경로). config 없으면 load_config() 사용."""
    if config is None:
        config = load_config()
    cfg = config.get("camera", {})
    save_dir = (cfg.get("save_dir") or "").strip() or None
    if not save_dir:
        return os.path.abspath(DEFAULT_PHOTOS_DIR)
    if os.path.isabs(save_dir):
        return save_dir
    base = os.path.dirname(CONFIG_PATH)
    return os.path.abspath(os.path.join(base, save_dir))


def get_status_path(config=None):
    """camera_status.json 경로 (사진 디렉터리와 동일)."""
    return os.path.join(get_photos_dir(config), STATUS_FILENAME)


def get_exposure_settings_path(config=None):
    """웹에서 저장한 노출 설정 파일 경로 (data/camera_exposure.json)."""
    base = os.path.dirname(CONFIG_PATH)
    data_dir = os.path.join(base, "data")
    return os.path.join(data_dir, EXPOSURE_SETTINGS_FILENAME)


def load_exposure_settings(config=None):
    """data/camera_exposure.json 로드. 없으면 기본값 복사본 반환."""
    path = get_exposure_settings_path(config)
    out = {k: dict(v) for k, v in DEFAULT_EXPOSURE.items()}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for band in ("day", "evening", "night"):
                if isinstance(saved.get(band), dict):
                    for key in ("shutter", "gain", "ev", "awb"):
                        if key in saved[band]:
                            out[band][key] = saved[band][key]
        except Exception:
            pass
    return out


def save_exposure_settings(settings, config=None):
    """웹에서 설정한 노출값 저장."""
    path = get_exposure_settings_path(config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _get_exposure_profile(now=None, config=None):
    """
    현재 시각 기준 노출 프로필 반환.
    웹에서 저장한 값(data/camera_exposure.json) 우선, 없으면 기본값.
    낮(06~18) / 저녁(05~06, 18~22) / 야간(22~05)
    """
    bands = load_exposure_settings(config)
    if now is None:
        now = datetime.now()
    h = now.hour
    if 6 <= h < 18:
        return dict(bands["day"])
    if (5 <= h < 6) or (18 <= h < 22):
        return dict(bands["evening"])
    return dict(bands["night"])


def capture_once_rpicam(save_path, config=None):
    """rpicam-still로 1장 촬영 (시간대별 노출 적용, 웹 설정 반영)."""
    if config is None:
        config = load_config()
    profile = _get_exposure_profile(config=config)
    cmd = [
        "rpicam-still",
        "-o", save_path,
        "--timeout", "2000",
        "--width", "1280",
        "--height", "720",
        "--shutter", str(profile["shutter"]),
        "--gain", str(profile["gain"]),
        "--ev", str(profile["ev"]),
        "--awb", profile["awb"],
        "--denoise", "auto",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print("rpicam-still error:", e)
        return False


def capture_once_picamera2(save_path):
    """Pi 공식 카메라 (picamera2) 폴백."""
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
    """USB 웹캠 (opencv) 폴백."""
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


def upload_to_drive(file_path, config=None):
    """rclone으로 원격 업로드. 성공 시 True."""
    if config is None:
        config = load_config()
    cfg = config.get("camera", {})
    remote = (cfg.get("rclone_remote") or "").strip()
    remote_path = (cfg.get("rclone_path") or "SmartFarmPhotos").strip()
    if not remote:
        return False
    dest = "{}:{}".format(remote, remote_path.rstrip("/"))
    try:
        subprocess.run(
            ["rclone", "copy", file_path, dest],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print("rclone error:", e)
        return False


def write_status(photos_dir, message, success=True, config=None):
    """camera_status.json 기록 (웹 API에서 사용)."""
    path = get_status_path(config)
    try:
        os.makedirs(photos_dir, exist_ok=True)
        data = {
            "message": message,
            "success": success,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("write_status error:", e)


def main():
    import sys
    config = load_config()
    cfg = config.get("camera", {})
    save_dir = get_photos_dir(config)
    os.makedirs(save_dir, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.jpg")
    save_path = os.path.join(save_dir, filename)

    if "once" not in (sys.argv[1:] or ["once"]):
        return

    captured = False
    if capture_once_rpicam(save_path, config):
        captured = True
    elif capture_once_picamera2(save_path):
        captured = True
    elif capture_once_opencv(save_path):
        captured = True

    if not captured:
        write_status(save_dir, "촬영 실패 (카메라 사용 불가)", success=False, config=config)
        print("Capture failed (no camera backend available?)")
        return

    print("Saved:", save_path)
    upload_ok = upload_to_drive(save_path, config)
    if upload_ok:
        msg = "{} 촬영 및 드라이브 업로드 완료".format(filename)
        if cfg.get("delete_after_upload"):
            try:
                os.remove(save_path)
            except OSError:
                pass
    else:
        msg = "{} 촬영 완료 (업로드 미설정 또는 실패)".format(filename)
    write_status(save_dir, msg, success=True, config=config)

if __name__ == "__main__":
    main()
