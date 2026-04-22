from __future__ import annotations

import json
from pathlib import Path

APP_NAME = 'MSFSHangar'
PRIMARY_CONFIG = 'hangar_bootstrap.json'
LEGACY_CONFIG = 'bootstrap.json'


def _candidate_paths(base_dir: Path) -> list[Path]:
    return [base_dir / PRIMARY_CONFIG, base_dir / LEGACY_CONFIG]


def resolve_bootstrap_path_for_write(base_dir: Path) -> Path:
    for path in _candidate_paths(base_dir):
        if path.exists():
            return path
    return base_dir / PRIMARY_CONFIG


def load_bootstrap_config(base_dir: Path) -> dict:
    for path in _candidate_paths(base_dir):
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_bootstrap_config(config: dict, base_dir: Path) -> None:
    path = resolve_bootstrap_path_for_write(base_dir)
    path.write_text(json.dumps(config or {}, indent=2, ensure_ascii=False), encoding='utf-8')


def get_forced_storage_root(base_dir: Path) -> str:
    cfg = load_bootstrap_config(base_dir)
    return str(cfg.get('forced_storage_root') or '').strip()


def get_library_profiles(base_dir: Path) -> list[dict]:
    cfg = load_bootstrap_config(base_dir)
    profiles = cfg.get('library_profiles') or []
    if not isinstance(profiles, list):
        return []
    cleaned: list[dict] = []
    for profile in profiles:
        if isinstance(profile, dict):
            cleaned.append(profile)
    return cleaned


def get_active_profile_id(base_dir: Path) -> str:
    cfg = load_bootstrap_config(base_dir)
    return str(cfg.get('active_profile_id') or '').strip()


def get_active_profile(base_dir: Path) -> dict | None:
    active_id = get_active_profile_id(base_dir)
    profiles = get_library_profiles(base_dir)
    if active_id:
        for profile in profiles:
            if str(profile.get('id') or '').strip() == active_id:
                return profile
    forced = get_forced_storage_root(base_dir)
    if forced:
        for profile in profiles:
            if str(profile.get('storage_root') or '').strip() == forced:
                return profile
    return None
