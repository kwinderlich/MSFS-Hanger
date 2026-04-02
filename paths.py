from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

APP_NAME = "MSFSHangar"
BASE_DIR = Path(__file__).parent
BUNDLED_DATA_DIR = BASE_DIR / "data"
BUNDLED_DB_PATH = BUNDLED_DATA_DIR / "hangar.db"
BUNDLED_SETTINGS_PATH = BUNDLED_DATA_DIR / "settings.json"


def _user_data_root() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root)
        return Path.home() / "AppData" / "Local"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "share"


USER_DATA_DIR = _user_data_root() / APP_NAME
DB_PATH = USER_DATA_DIR / "hangar.db"
SETTINGS_JSON_PATH = USER_DATA_DIR / "settings.json"
LOG_DIR = USER_DATA_DIR / "logs"
BROWSER_PROFILE_DIR = USER_DATA_DIR / "browser_profile"
PID_FILE = USER_DATA_DIR / "backend.pid"
CACHE_ROOT = USER_DATA_DIR / "browser_profile"


def ensure_user_data_dirs() -> Path:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return USER_DATA_DIR


def initialize_user_data() -> None:
    ensure_user_data_dirs()
    # One-time migration: if the user previously stored data in the app folder,
    # move it to LocalAppData so future zip upgrades do not overwrite it.
    if not DB_PATH.exists() and BUNDLED_DB_PATH.exists() and BUNDLED_DB_PATH.stat().st_size > 0:
        try:
            shutil.copy2(BUNDLED_DB_PATH, DB_PATH)
        except Exception:
            pass

    if not SETTINGS_JSON_PATH.exists():
        initial = {}
        if BUNDLED_SETTINGS_PATH.exists():
            try:
                initial = json.loads(BUNDLED_SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception:
                initial = {}
        try:
            SETTINGS_JSON_PATH.write_text(json.dumps(initial, indent=2), encoding="utf-8")
        except Exception:
            pass


def load_settings_file() -> dict[str, str]:
    initialize_user_data()
    try:
        raw = json.loads(SETTINGS_JSON_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): v for k, v in raw.items()}
    except Exception:
        pass
    return {}


def save_settings_file(settings: dict[str, str]) -> None:
    initialize_user_data()
    serializable = {}
    for k, v in settings.items():
        serializable[str(k)] = v
    SETTINGS_JSON_PATH.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
