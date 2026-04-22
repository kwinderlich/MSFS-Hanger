from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import main as hanger_main

if __name__ == '__main__':
    hanger_main.main()
