from __future__ import annotations

import json
from pathlib import Path

APP_NAME = 'MSFSHangar'
CONFIG_FILENAME = 'hangar_bootstrap.json'


def _config_path(base_dir: Path) -> Path:
    return base_dir / CONFIG_FILENAME


def resolve_bootstrap_path_for_write(base_dir: Path) -> Path:
    return _config_path(base_dir)


def load_bootstrap_config(base_dir: Path) -> dict:
    path = _config_path(base_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_bootstrap_config(config: dict, base_dir: Path) -> None:
    path = _config_path(base_dir)
    path.write_text(json.dumps(config or {}, indent=2), encoding='utf-8')


def get_forced_storage_root(base_dir: Path) -> str:
    cfg = load_bootstrap_config(base_dir)
    return str((cfg.get('forced_storage_root') or '')).strip()


def get_library_profiles(base_dir: Path) -> list[dict]:
    cfg = load_bootstrap_config(base_dir)
    profiles = cfg.get('library_profiles') or []
    return profiles if isinstance(profiles, list) else []


def get_active_profile(base_dir: Path) -> dict | None:
    active_id = get_active_profile_id(base_dir)
    for profile in get_library_profiles(base_dir):
        if str(profile.get('id') or '') == active_id:
            return profile
    return None


def get_active_profile_id(base_dir: Path) -> str:
    cfg = load_bootstrap_config(base_dir)
    return str((cfg.get('active_profile_id') or '')).strip()
