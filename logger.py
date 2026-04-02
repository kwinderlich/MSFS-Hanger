"""
MSFS Hangar — Logging & Diagnostics
======================================
Central logging for all modules. One import, consistent logs everywhere.

Log files:
  data/logs/hangar_YYYY-MM-DD.log   — daily rotating, all INFO+, kept 14 days
  data/logs/errors.log              — errors only, never rotated (permanent record)
  data/logs/last_startup.json       — snapshot of startup state for diagnosis

Usage in any module:
    from logger import get_logger
    log = get_logger(__name__)

    log.debug("Detailed trace: %s", value)       # dev only, not in prod log
    log.info("Scan started for %s", folder)       # normal operations
    log.warning("Manifest missing in %s", path)   # unexpected but recoverable
    log.error("DB write failed: %s", err)         # something broke
    log.error("Details", exc_info=True)           # includes full traceback
    log.critical("Cannot start server", exc_info=True)

Viewing logs:
  - Open data/logs/hangar_YYYY-MM-DD.log in any text editor (Notepad, VS Code)
  - Visit http://localhost:7891/api/diag in browser for live diagnostic report
  - data/logs/errors.log for a permanent record of all errors ever
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from paths import BASE_DIR, LOG_DIR, initialize_user_data

# ── Paths ──────────────────────────────────────────────────────────────────
initialize_user_data()
DAILY_LOG    = LOG_DIR / f"hangar_{datetime.now():%Y-%m-%d}.log"
ERROR_LOG    = LOG_DIR / "errors.log"
STARTUP_FILE = LOG_DIR / "last_startup.json"

# ── Log format ─────────────────────────────────────────────────────────────
LOG_FMT  = "%(asctime)s  %(levelname)-8s  %(name)-22s  %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"
_setup_done = False


def setup_logging(level: str = "INFO"):
    """
    Call once from main.py before anything else.
    Sets up rotating daily file, permanent error file, and console handler.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt  = logging.Formatter(LOG_FMT, DATE_FMT)

    # 1. Daily rotating file — INFO and above, 14 days history
    try:
        fh = logging.handlers.TimedRotatingFileHandler(
            str(DAILY_LOG), when="midnight", backupCount=14, encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as e:
        print(f"[logger] Could not create daily log: {e}")

    # 2. Permanent error log — ERROR and above, never rotated
    try:
        eh = logging.FileHandler(str(ERROR_LOG), encoding="utf-8")
        eh.setLevel(logging.ERROR)
        eh.setFormatter(fmt)
        root.addHandler(eh)
    except Exception as e:
        print(f"[logger] Could not create error log: {e}")

    # 3. Console — WARNING and above (keeps terminal readable during normal use)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("  %(levelname)-8s %(name)s — %(message)s"))
    root.addHandler(ch)

    # 4. Catch all unhandled exceptions and log them before crash
    def _uncaught(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.critical("UNHANDLED EXCEPTION — app will crash",
                         exc_info=(exc_type, exc_value, exc_tb))
    sys.excepthook = _uncaught

    # 5. Silence noisy third-party loggers
    for noisy in ["uvicorn.access", "uvicorn.error", "watchfiles",
                  "asyncio", "multipart"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    log = get_logger("startup")
    log.info("=" * 60)
    log.info("MSFS Hangar starting up  |  Python %s  |  %s",
             sys.version.split()[0], platform.system())
    log.info("Log file : %s", DAILY_LOG)
    log.info("Error log: %s", ERROR_LOG)
    log.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Always pass __name__ from the calling module."""
    return logging.getLogger(name)


# ── Startup snapshot ───────────────────────────────────────────────────────

def write_startup_snapshot(settings: dict):
    """
    Write a JSON file capturing the startup environment.
    This makes it easy to answer 'it worked yesterday, what changed?'
    """
    def _pkg_version(name: str) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version(name)
        except Exception:
            return "not installed"

    snap = {
        "timestamp":      datetime.now().isoformat(),
        "python_version": sys.version,
        "platform":       platform.platform(),
        "machine":        platform.machine(),
        "cwd":            str(Path.cwd()),
        "base_dir":       str(BASE_DIR),
        "log_dir":        str(LOG_DIR),
        "settings": {
            k: ("***" if "key" in k.lower() else v)   # redact API keys
            for k, v in settings.items()
        },
        "packages": {
            pkg: _pkg_version(pkg)
            for pkg in ["fastapi", "uvicorn", "aiosqlite", "websockets",
                        "python-multipart"]
        },
    }
    try:
        STARTUP_FILE.write_text(json.dumps(snap, indent=2, default=str),
                                encoding="utf-8")
    except Exception as e:
        get_logger("startup").warning("Could not write startup snapshot: %s", e)
    return snap


# ── Diagnostic report ──────────────────────────────────────────────────────

def build_diag_report(extra: dict = None) -> dict:
    """
    Build a structured diagnostic report for the /api/diag endpoint.
    Returns dict with recent logs, error log, and startup snapshot.
    """
    def _tail(path: Path, n: int) -> str:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-n:])
        except FileNotFoundError:
            return f"(file not found: {path})"
        except Exception as e:
            return f"(could not read: {e})"

    def _list_logs() -> list[dict]:
        result = []
        try:
            for p in sorted(LOG_DIR.glob("*.log"), reverse=True)[:10]:
                result.append({
                    "name":     p.name,
                    "size_kb":  round(p.stat().st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                })
        except Exception:
            pass
        return result

    startup = {}
    try:
        startup = json.loads(STARTUP_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {
        "status":          "ok",
        "timestamp":       datetime.now().isoformat(),
        "python":          sys.version,
        "platform":        platform.platform(),
        "log_dir":         str(LOG_DIR),
        "log_files":       _list_logs(),
        "recent_log":      _tail(DAILY_LOG, 150),
        "recent_errors":   _tail(ERROR_LOG,  50),
        "startup":         startup,
        **(extra or {}),
    }
