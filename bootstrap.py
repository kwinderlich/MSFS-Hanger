from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import bootstrap_cfg
from native_dialogs import pick_or_create_folder

BASE_DIR = Path(__file__).parent


def _pick_folder(initial: str = '') -> str:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showinfo('MSFS Hangar first-time setup', 'Choose the parent folder or existing folder to store MSFS Hangar user files for the default profile “MSFS 2024”. After browsing, you can use the folder as-is or create a new folder inside it and use that immediately.', parent=root)
        root.destroy()
    except Exception:
        pass
    return pick_or_create_folder(initial or str(BASE_DIR), 'Choose MSFS Hangar base app folder')


def _ensure_first_run_storage() -> tuple[dict, str]:
    cfg = bootstrap_cfg.load_bootstrap_config(BASE_DIR)
    root = bootstrap_cfg.get_forced_storage_root(cfg, BASE_DIR)
    if root:
        return cfg, root
    chosen = _pick_folder(str(BASE_DIR))
    if not chosen:
        raise SystemExit('MSFS Hangar setup cancelled before a base app folder was selected.')
    chosen_path = str(Path(chosen).expanduser())
    Path(chosen_path).mkdir(parents=True, exist_ok=True)
    profile = bootstrap_cfg.make_profile(bootstrap_cfg.DEFAULT_PROFILE_NAME, bootstrap_cfg.DEFAULT_PLATFORM, chosen_path, bootstrap_cfg.DEFAULT_PROFILE_ID)
    cfg = {
        'version': 1,
        'forced_storage_root': chosen_path,
        'active_profile_id': profile['id'],
        'library_profiles': [profile],
    }
    path = bootstrap_cfg.save_bootstrap_config(cfg, BASE_DIR)
    print(f'Created bootstrap config: {path}', flush=True)
    print(f'Initial app-data folder: {chosen_path}', flush=True)
    return bootstrap_cfg.load_bootstrap_config(BASE_DIR), chosen_path




def _try_remove_pending_root(cfg: dict, active_root: str) -> dict:
    pending = str((cfg or {}).get('pending_delete_root') or '').strip()
    if not pending:
        return cfg
    try:
        pending_path = Path(pending).expanduser().resolve()
        active_path = Path(active_root).expanduser().resolve()
    except Exception:
        pending_path = Path(pending).expanduser()
        active_path = Path(active_root).expanduser()
    if str(pending_path) == str(active_path):
        return cfg
    if pending_path.exists():
        try:
            import shutil
            shutil.rmtree(pending_path)
            print(f'Removed previous app-data folder: {pending_path}', flush=True)
        except Exception as exc:
            print(f'Could not remove previous app-data folder {pending_path}: {exc}', flush=True)
            return cfg
    cfg = dict(cfg or {})
    cfg['pending_delete_root'] = ''
    bootstrap_cfg.save_bootstrap_config(cfg, BASE_DIR)
    return bootstrap_cfg.load_bootstrap_config(BASE_DIR)


def main() -> int:
    cfg, root = _ensure_first_run_storage()
    cfg = _try_remove_pending_root(cfg, root)
    root = bootstrap_cfg.get_forced_storage_root(cfg, BASE_DIR) or root
    env = os.environ.copy()
    env['HANGAR_USER_DATA_DIR'] = root
    active = bootstrap_cfg.get_active_profile(cfg) or {}
    if active.get('id'):
        env['HANGAR_ACTIVE_PROFILE_ID'] = str(active.get('id'))
    if active.get('name'):
        env['HANGAR_ACTIVE_PROFILE_NAME'] = str(active.get('name'))
    cmd = [sys.executable, 'main.py']
    return subprocess.call(cmd, cwd=str(BASE_DIR), env=env)


if __name__ == '__main__':
    raise SystemExit(main())
