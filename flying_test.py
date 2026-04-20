from __future__ import annotations

import copy

_PID_TEST_CONFIG = {
    "modes": [
        {"code": "PID", "label": "PID", "title": "pid surface controller"},
        {"code": "LVL", "label": "LVL", "title": "level hold tuning"},
        {"code": "ALT", "label": "ALT", "title": "altitude hold tuning"},
        {"code": "CRS", "label": "CRS", "title": "course line follow"},
        {"code": "SPD", "label": "SPD", "title": "speed hold tuning"},
    ],
    "notes": [
        "PID Test is the Gemini-inspired control-surface path: Python loop, route geometry, and surface commands.",
        "This screen is intended for controller tuning and smoothness checks, not the final map-first virtual-pilot experience.",
    ],
}


def get_flying_test_config() -> dict:
    return copy.deepcopy(_PID_TEST_CONFIG)
