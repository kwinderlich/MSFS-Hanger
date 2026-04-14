from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_NAME = "MSFSHangar"
DEFAULT_PROFILE_ID = "default-msfs2024"
DEFAULT_PROFILE_NAME = "MSFS 2024"
DEFAULT_PLATFORM = "msfs2024"


def _home_dir() -> Path:
    raw = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(raw)


def default_bootstrap_path(base_dir: Optional[Path] = None) -> Path:
    return _home_dir() / f"{APP_NAME}_bootstrap.json"


def candidate_bootstrap_paths(base_dir: Optional[Path] = None) -> list[Path]:
    items = []
    env_path = os.environ.get('HANGAR_BOOTSTRAP_PATH', '').strip()
    if env_path:
        items.append(Path(env_path).expanduser())
    items.append(default_bootstrap_path(base_dir))
    if base_dir:
        items.append(Path(base_dir) / f"{APP_NAME}_bootstrap.json")
    seen = set(); out = []
    for p in items:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def resolve_bootstrap_path_for_write(base_dir: Optional[Path] = None) -> Path:
    env_path = os.environ.get('HANGAR_BOOTSTRAP_PATH', '').strip()
    if env_path:
        return Path(env_path).expanduser()
    return default_bootstrap_path(base_dir)


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def make_profile(name: str, platform: str, storage_root: str, profile_id: Optional[str] = None) -> dict:
    return {
        'id': profile_id or DEFAULT_PROFILE_ID,
        'name': (name or DEFAULT_PROFILE_NAME).strip() or DEFAULT_PROFILE_NAME,
        'platform': (platform or DEFAULT_PLATFORM).strip() or DEFAULT_PLATFORM,
        'storage_root': str(Path(storage_root).expanduser()) if storage_root else '',
        'created_at': _iso_now(),
        'updated_at': _iso_now(),
    }


def normalize_bootstrap_config(config: Optional[dict]) -> dict:
    cfg = dict(config or {})
    profiles = cfg.get('library_profiles')
    if not isinstance(profiles, list):
        profiles = []
    norm = []
    seen = set()
    for item in profiles:
        if not isinstance(item, dict):
            continue
        pid = str(item.get('id') or '').strip() or f"profile-{len(norm)+1}"
        if pid in seen:
            continue
        seen.add(pid)
        root = str(item.get('storage_root') or '').strip()
        norm.append({
            'id': pid,
            'name': str(item.get('name') or 'Profile').strip() or 'Profile',
            'platform': str(item.get('platform') or DEFAULT_PLATFORM).strip() or DEFAULT_PLATFORM,
            'storage_root': str(Path(root).expanduser()) if root else '',
            'created_at': str(item.get('created_at') or _iso_now()),
            'updated_at': str(item.get('updated_at') or item.get('created_at') or _iso_now()),
        })
    forced_root = str(cfg.get('forced_storage_root') or '').strip()
    active_id = str(cfg.get('active_profile_id') or '').strip()
    if not norm and forced_root:
        norm = [make_profile(DEFAULT_PROFILE_NAME, DEFAULT_PLATFORM, forced_root, DEFAULT_PROFILE_ID)]
        active_id = DEFAULT_PROFILE_ID
    if norm:
        if not active_id or not any(p['id'] == active_id for p in norm):
            active_id = norm[0]['id']
        active = next((p for p in norm if p['id'] == active_id), None)
        if active and active.get('storage_root'):
            forced_root = active['storage_root']
    pending_delete_root = str(cfg.get('pending_delete_root') or '').strip()
    cfg['library_profiles'] = norm
    cfg['active_profile_id'] = active_id
    cfg['forced_storage_root'] = forced_root
    cfg['pending_delete_root'] = str(Path(pending_delete_root).expanduser()) if pending_delete_root else ''
    cfg['version'] = int(cfg.get('version') or 1)
    return cfg


def load_bootstrap_config(base_dir: Optional[Path] = None) -> dict:
    for path in candidate_bootstrap_paths(base_dir):
        try:
            if path.exists():
                raw = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    cfg = normalize_bootstrap_config(raw)
                    cfg['_bootstrap_path'] = str(path)
                    return cfg
        except Exception:
            continue
    cfg = normalize_bootstrap_config({})
    cfg['_bootstrap_path'] = str(resolve_bootstrap_path_for_write(base_dir))
    return cfg


def save_bootstrap_config(config: dict, base_dir: Optional[Path] = None) -> Path:
    path = resolve_bootstrap_path_for_write(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = normalize_bootstrap_config(config)
    cfg.pop('_bootstrap_path', None)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    return path


def get_library_profiles(config: Optional[dict] = None, base_dir: Optional[Path] = None) -> list[dict]:
    cfg = normalize_bootstrap_config(config) if config is not None else load_bootstrap_config(base_dir)
    return list(cfg.get('library_profiles') or [])


def get_active_profile(config: Optional[dict] = None, base_dir: Optional[Path] = None) -> Optional[dict]:
    cfg = normalize_bootstrap_config(config) if config is not None else load_bootstrap_config(base_dir)
    active_id = str(cfg.get('active_profile_id') or '').strip()
    for item in cfg.get('library_profiles') or []:
        if item.get('id') == active_id:
            return dict(item)
    return None


def get_active_profile_id(config: Optional[dict] = None, base_dir: Optional[Path] = None) -> str:
    cfg = normalize_bootstrap_config(config) if config is not None else load_bootstrap_config(base_dir)
    return str(cfg.get('active_profile_id') or '')


def get_forced_storage_root(config: Optional[dict] = None, base_dir: Optional[Path] = None) -> str:
    cfg = normalize_bootstrap_config(config) if config is not None else load_bootstrap_config(base_dir)
    active = get_active_profile(cfg)
    if active and str(active.get('storage_root') or '').strip():
        return str(active.get('storage_root') or '').strip()
    return str(cfg.get('forced_storage_root') or '').strip()
