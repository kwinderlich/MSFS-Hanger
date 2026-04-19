from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import bootstrap_cfg  # noqa: E402


def _ensure_first_run_storage() -> tuple[dict, str]:
    cfg = bootstrap_cfg.load_bootstrap_config(BASE_DIR)
    root = bootstrap_cfg.get_forced_storage_root(BASE_DIR)
    return cfg, root


def main() -> int:
    _ensure_first_run_storage()
    import main as hangar_main  # noqa: E402
    return int(hangar_main.main() or 0)


if __name__ == '__main__':
    raise SystemExit(main())
