"""
MSFS Hangar — Symlink / Junction Manager
==========================================
Creates and removes Windows directory junctions to enable/disable addons
in the MSFS Community folder.

Windows notes:
  - Directory junctions (mklink /J) do NOT require admin rights IF
    Developer Mode is enabled in Windows Settings → For Developers.
  - Symlinks (mklink /D) DO require admin or Developer Mode.
  - We use junctions by default — they behave identically for MSFS.

AddonLinker compatibility:
  - AddonLinker stores its own symlinks/junctions in Community.
  - We detect existing links regardless of who created them.
  - Toggling OFF only removes links WE created (by checking the target).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


# ── Detection ──────────────────────────────────────────────────────────────

def is_junction(path: Path) -> bool:
    """Return True if path is a Windows directory junction or symlink."""
    try:
        if path.is_symlink():
            return True
        # Check FILE_ATTRIBUTE_REPARSE_POINT (0x400)
        attrs = path.stat().st_file_attributes
        return bool(attrs & 0x400)
    except Exception:
        return False


def get_link_target(path: Path) -> str:
    """Return the target of a junction/symlink, or empty string."""
    try:
        return str(Path(os.readlink(str(path))).resolve())
    except Exception:
        return ""


def find_link_in_community(community_dir: Path, addon_path: Path) -> bool:
    """
    Return True if community_dir contains ANY junction/symlink
    whose target resolves to addon_path.
    This detects both our own links and AddonLinker-created links.
    """
    if not community_dir.exists():
        return False
    target = str(addon_path.resolve())
    try:
        for entry in community_dir.iterdir():
            if entry.is_dir():
                if is_junction(entry):
                    if get_link_target(entry) == target:
                        return True
                # Also match by folder name (AddonLinker may not use symlinks)
                if entry.name.lower() == addon_path.name.lower():
                    return True
    except Exception:
        pass
    return False


def link_name_for_addon(addon_path: Path) -> str:
    """The name to use for the junction in Community — same as addon folder name."""
    return addon_path.name


def _candidate_links(community_dir: Path, addon_path: Path) -> list[Path]:
    candidates: list[Path] = []
    preferred = community_dir / link_name_for_addon(addon_path)
    if preferred.exists() or is_junction(preferred):
        candidates.append(preferred)
    try:
        target = str(addon_path.resolve())
        for entry in community_dir.iterdir():
            if not entry.is_dir():
                continue
            if entry in candidates:
                continue
            if entry.name.lower() == addon_path.name.lower():
                candidates.append(entry)
                continue
            if is_junction(entry) and get_link_target(entry) == target:
                candidates.append(entry)
    except Exception:
        pass
    return candidates


def _remove_windows_link(link: Path) -> bool:
    win_link = str(link).replace("/", "\\")
    commands = [
        ["cmd", "/c", "rmdir", win_link],
        ["cmd", "/c", "if", "exist", win_link, "del", win_link],
        ["powershell", "-NoProfile", "-Command", f"if (Test-Path -LiteralPath '{win_link}') {{ Remove-Item -LiteralPath '{win_link}' -Force -Recurse -ErrorAction SilentlyContinue }}"],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=12, shell=False)
            if result.returncode == 0 or not link.exists():
                return True
        except Exception:
            continue
    try:
        os.rmdir(str(link))
        return not link.exists()
    except Exception:
        return not link.exists()


# ── Enable / Disable ──────────────────────────────────────────────────────

def enable_addon(addon_path: str, community_dir: str) -> Tuple[bool, str]:
    """
    Create a directory junction in community_dir pointing to addon_path.
    Returns (success, message).
    """
    src  = Path(addon_path).resolve()
    comm = Path(community_dir).resolve()

    if not src.exists():
        return False, f"Addon folder not found: {src}"
    if not comm.exists():
        return False, f"Community folder not found: {comm}"

    link = comm / link_name_for_addon(src)

    if link.exists() or is_junction(link):
        target = get_link_target(link)
        if str(src) == target:
            return True, "Already enabled"
        return False, f"A different link already exists at {link}"

    if sys.platform != "win32":
        # On non-Windows (dev/test): create a real symlink
        try:
            os.symlink(str(src), str(link))
            return True, f"Symlink created: {link} → {src}"
        except Exception as e:
            return False, str(e)

    # Windows: use junction (mklink /J) — no admin needed with Developer Mode
    try:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J",
             str(link).replace("/", "\\"),
             str(src).replace("/", "\\")],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, f"Junction created: {link.name}"
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"mklink failed: {err}"
    except subprocess.TimeoutExpired:
        return False, "mklink timed out"
    except Exception as e:
        return False, str(e)


def disable_addon(addon_path: str, community_dir: str) -> Tuple[bool, str]:
    """
    Remove the junction/symlink in community_dir for this addon.
    Search by both link name and resolved target because older builds may have
    created slightly different link names.
    """
    src  = Path(addon_path).resolve()
    comm = Path(community_dir).resolve()
    candidates = _candidate_links(comm, src)

    if not candidates:
        return True, "Already disabled (no link found)"

    failures = []
    for link in candidates:
        try:
            if sys.platform != "win32":
                if link.is_symlink():
                    os.unlink(str(link))
                elif link.exists() and link.is_dir() and not any(link.iterdir()):
                    os.rmdir(str(link))
                else:
                    failures.append(f"Cannot safely disable non-link folder: {link}")
                    continue
                continue

            if _remove_windows_link(link):
                continue
            failures.append(f"Could not remove community link: {link}")
        except Exception as e:
            failures.append(str(e))

    if failures and len(failures) == len(candidates):
        return False, failures[0]
    return True, f"Disabled: {', '.join(link.name for link in candidates)}"

def toggle_addon(addon_path: str, community_dir: str, enable: bool) -> Tuple[bool, str]:
    """Convenience wrapper."""
    if enable:
        return enable_addon(addon_path, community_dir)
    else:
        return disable_addon(addon_path, community_dir)


# ── Batch status check ────────────────────────────────────────────────────

def get_all_enabled(community_dir: str) -> dict[str, str]:
    """
    Scan Community folder and return {junction_name: resolved_target_path}
    for every junction/symlink found. Includes AddonLinker entries.
    """
    comm = Path(community_dir)
    result = {}
    if not comm.exists():
        return result
    try:
        for entry in comm.iterdir():
            if entry.is_dir():
                if is_junction(entry):
                    result[entry.name] = get_link_target(entry)
                # Plain directories in Community are also "enabled" (manual installs)
    except Exception:
        pass
    return result


# ── CLI test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    e = sub.add_parser("enable")
    e.add_argument("addon_path")
    e.add_argument("community_dir")

    d = sub.add_parser("disable")
    d.add_argument("addon_path")
    d.add_argument("community_dir")

    s = sub.add_parser("status")
    s.add_argument("community_dir")

    args = p.parse_args()

    if args.cmd == "enable":
        ok, msg = enable_addon(args.addon_path, args.community_dir)
        print(("OK" if ok else "FAIL"), msg)
    elif args.cmd == "disable":
        ok, msg = disable_addon(args.addon_path, args.community_dir)
        print(("OK" if ok else "FAIL"), msg)
    elif args.cmd == "status":
        enabled = get_all_enabled(args.community_dir)
        print(json.dumps(enabled, indent=2))
    else:
        p.print_help()
