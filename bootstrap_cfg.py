from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "MSFSHangar"
BOOTSTRAP_FILENAME = "hangar_bootstrap.json"
LEGACY_BOOTSTRAP_FILENAMES = ("hangar_bootstrap.json", "bootstrap.json")


def _default_root(base_dir: Path | None = None) -> Path:
    env = os.environ.get("HANGAR_BOOTSTRAP_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    return base / APP_NAME


def _candidate_bootstrap_paths(base_dir: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    explicit_file = os.environ.get("HANGAR_BOOTSTRAP_FILE", "").strip()
    if explicit_file:
        candidates.append(Path(explicit_file).expanduser())
    search_dirs: list[Path] = []
    if base_dir:
        search_dirs.append(Path(base_dir))
    try:
        search_dirs.append(Path.cwd())
    except Exception:
        pass
    script_dir = Path(__file__).resolve().parent
    if script_dir not in search_dirs:
        search_dirs.append(script_dir)
    default_root = _default_root(base_dir)
    if default_root not in search_dirs:
        search_dirs.append(default_root)
    seen: set[str] = set()
    for folder in search_dirs:
        try:
            folder = folder.resolve()
        except Exception:
            folder = folder.expanduser()
        key = str(folder).lower() if os.name == 'nt' else str(folder)
        if key in seen:
            continue
        seen.add(key)
        for name in LEGACY_BOOTSTRAP_FILENAMES:
            candidates.append(folder / name)
    return candidates


def resolve_bootstrap_path(base_dir: Path | None = None, *, for_write: bool = False) -> Path:
    for candidate in _candidate_bootstrap_paths(base_dir):
        if candidate.exists():
            return candidate
    if for_write and base_dir:
        return Path(base_dir) / BOOTSTRAP_FILENAME
    return _default_root(base_dir) / BOOTSTRAP_FILENAME


def resolve_bootstrap_path_for_write(base_dir: Path | None = None) -> Path:
    return resolve_bootstrap_path(base_dir, for_write=True)


def _default_config(base_dir: Path | None = None) -> dict[str, Any]:
    root = _default_root(base_dir)
    return {
        "forced_storage_root": "",
        "active_profile_id": "default-msfs2024",
        "library_profiles": [
            {
                "id": "default-msfs2024",
                "name": "MSFS 2024",
                "platform": "msfs2024",
                "storage_root": str(root),
                "is_default": True,
            }
        ],
        "pending_delete_root": "",
    }


def load_bootstrap_config(base_dir: Path | None = None) -> dict[str, Any]:
    path = resolve_bootstrap_path(base_dir)
    if not path.exists():
        return _default_config(base_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = _default_config(base_dir)
            merged.update(data)
            if not isinstance(merged.get("library_profiles"), list) or not merged.get("library_profiles"):
                merged["library_profiles"] = _default_config(base_dir)["library_profiles"]
            return merged
    except Exception:
        pass
    return _default_config(base_dir)


def save_bootstrap_config(config: dict[str, Any], base_dir: Path | None = None) -> None:
    path = resolve_bootstrap_path_for_write(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = _default_config(base_dir)
    if isinstance(config, dict):
        merged.update(config)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def get_forced_storage_root(base_dir: Path | None = None) -> str:
    cfg = load_bootstrap_config(base_dir)
    return str(cfg.get("forced_storage_root") or "").strip()


def get_library_profiles(base_dir: Path | None = None) -> list[dict[str, Any]]:
    cfg = load_bootstrap_config(base_dir)
    profiles = cfg.get("library_profiles")
    if isinstance(profiles, list) and profiles:
        return [p for p in profiles if isinstance(p, dict)] or _default_config(base_dir)["library_profiles"]
    return _default_config(base_dir)["library_profiles"]


def get_active_profile_id(base_dir: Path | None = None) -> str:
    cfg = load_bootstrap_config(base_dir)
    active = str(cfg.get("active_profile_id") or "").strip()
    if active:
        return active
    profiles = get_library_profiles(base_dir)
    return str((profiles[0] or {}).get("id") or "default-msfs2024")


def get_active_profile(base_dir: Path | None = None) -> dict[str, Any] | None:
    active_id = get_active_profile_id(base_dir)
    for profile in get_library_profiles(base_dir):
        if str(profile.get("id") or "") == active_id:
            return profile
    profiles = get_library_profiles(base_dir)
    return profiles[0] if profiles else None
