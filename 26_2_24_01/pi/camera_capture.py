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
EXPOSURE_FIELDS = ("shutter", "gain", "ev", "awb")


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


def _hour_key(hour):
    return "{:02d}".format(int(hour))


def _default_profile_for_hour(hour):
    hour = int(hour)
    if 6 <= hour < 18:
        return dict(DEFAULT_EXPOSURE["day"])
    if hour == 5 or 18 <= hour < 22:
        return dict(DEFAULT_EXPOSURE["evening"])
    return dict(DEFAULT_EXPOSURE["night"])


def _default_hourly_exposure():
    return {_hour_key(hour): _default_profile_for_hour(hour) for hour in range(24)}


def _normalize_profile(target, raw):
    if not isinstance(raw, dict):
        return
    for key in EXPOSURE_FIELDS:
        if key not in raw:
            continue
        value = raw[key]
        if value in (None, ""):
            continue
        try:
            if key == "awb":
                target[key] = str(value)
            elif key in ("shutter", "ev"):
                target[key] = int(value)
            else:
                target[key] = float(value)
        except (TypeError, ValueError):
            continue


def normalize_exposure_settings(settings):
    """
    노출 설정을 시간별(00~23) 포맷으로 정규화.
    기존 day/evening/night 포맷도 읽어서 자동 확장한다.
    """
    out = _default_hourly_exposure()
    source = settings.get("hours") if isinstance(settings, dict) and isinstance(settings.get("hours"), dict) else settings
    has_hourly = False

    if isinstance(source, dict):
        for hour in range(24):
            key = _hour_key(hour)
            if isinstance(source.get(key), dict):
                _normalize_profile(out[key], source[key])
                has_hourly = True
            elif isinstance(source.get(hour), dict):
                _normalize_profile(out[key], source[hour])
                has_hourly = True

    if has_hourly:
        return out

    if isinstance(source, dict):
        for hour in range(24):
            if 6 <= hour < 18:
                band = "day"
            elif hour == 5 or 18 <= hour < 22:
                band = "evening"
            else:
                band = "night"
            if isinstance(source.get(band), dict):
                _normalize_profile(out[_hour_key(hour)], source[band])

    return out


def load_exposure_settings(config=None):
    """data/camera_exposure.json 로드. 없으면 시간별 기본값 반환."""
    path = get_exposure_settings_path(config)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return normalize_exposure_settings(json.load(f))
        except Exception:
            pass
    return _default_hourly_exposure()


def save_exposure_settings(settings, config=None):
    """웹에서 설정한 시간별 노출값 저장."""
    path = get_exposure_settings_path(config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalize_exposure_settings(settings), f, ensure_ascii=False, indent=2)


def _get_exposure_profile(now=None, config=None):
    """
    현재 시각 기준 노출 프로필 반환.
    웹에서 저장한 시간별 값(data/camera_exposure.json) 우선, 없으면 기본값.
    """
    settings = load_exposure_settings(config)
    if now is None:
        now = datetime.now()
    return dict(settings[_hour_key(now.hour)])


def capture_once_rpicam(save_path, config=None):
    """rpicam-still로 1장 촬영 (시간대별 노출 적용, 웹 설정 반영)."""
    if config is None:
        config = load_config()
    profile = _get_exposure_profile(config=config)
    cmd = [
        "rpicam-still",
        "-o", save_path,
        "--timeout", "2000",
        "--width", "1920",
        "--height", "1080",
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
